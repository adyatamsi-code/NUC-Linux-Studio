// SPDX-License-Identifier: GPL-2.0
#include "pr.h"

#include <acpi/video.h>
#include <dt-bindings/leds/common.h>
#include <linux/acpi.h>
#include <linux/init.h>
#include <linux/input.h>
#include <linux/input/sparse-keymap.h>
#include <linux/leds.h>
#include <linux/version.h>
#include <linux/i8042.h>
#include <linux/delay.h>
#include <linux/workqueue.h>

#include "events.h"
#include "misc.h"
#include "pdev.h"
#include "wmi.h"
#include "ec.h"

/* ========================================================================== */

#define KBD_BL_LED_SUFFIX ":" LED_FUNCTION_KBD_BACKLIGHT

/* ========================================================================== */

static struct {
	const char *guid;
	bool handler_installed;
} nuc_wmi_wmi_event_guids[] = {
	{ .guid = NUC_WMI_EVENT_70_GUID },
	{ .guid = NUC_WMI_EVENT_71_GUID },
	{ .guid = NUC_WMI_EVENT_72_GUID },
};

/*
 * Grace period (jiffies) after WMI handler installation during which
 * keyboard-backlight events are suppressed.  The EC delivers stale/queued
 * events the moment wmi_install_notify_handler() registers our callback,
 * which leads to spurious brightness toggles on every driver (re)load.
 */
#define WMI_GRACE_JIFFIES  (3 * HZ)
static unsigned long wmi_handler_installed_at;

static const struct key_entry nuc_wmi_wmi_hotkeys[] = {

	/* reported via keyboard controller */
	{ KE_IGNORE, 0x01, { KEY_CAPSLOCK }},
	{ KE_IGNORE, 0x02, { KEY_NUMLOCK }},
	{ KE_IGNORE, 0x03, { KEY_SCROLLLOCK }},

	/* reported via "video bus" */
	{ KE_IGNORE, 0x14, { KEY_BRIGHTNESSUP }},
	{ KE_IGNORE, 0x15, { KEY_BRIGHTNESSDOWN }},

	/* reported in automatic mode when rfkill state changes */
	{ KE_SW,     0x1a, {.sw = { SW_RFKILL_ALL, 1 }}},
	{ KE_SW,     0x1b, {.sw = { SW_RFKILL_ALL, 0 }}},

	/* touchpad toggle — KE_IGNORE: don't let GNOME handle it (fights daemon).
	 * Our daemon shows its own OSD notification via notify-send. */
	{ KE_IGNORE, 0x04, { KEY_F21 }},
	{ KE_IGNORE, 0x05, { KEY_F21 }},

	/* microphone mute button — handled by Intel HID, don't double-report */
	{ KE_IGNORE, 0x07, { KEY_MICMUTE }},
	{ KE_IGNORE, 0xb7, { KEY_MICMUTE }},

	/* performance profile button */
	{ KE_KEY,    0xb0, { KEY_PROG1 }},


	/* reported via keyboard controller */
	{ KE_IGNORE, 0x35, { KEY_MUTE }},
	{ KE_IGNORE, 0x36, { KEY_VOLUMEDOWN }},
	{ KE_IGNORE, 0x37, { KEY_VOLUMEUP }},

	/*
	 * not reported by other means when in manual mode,
	 * handled automatically when it automatic mode
	 */
	{ KE_KEY,    0xa4, { KEY_RFKILL }},
	{ KE_KEY,    0xb1, { KEY_KBDILLUMDOWN }},
	{ KE_KEY,    0xb2, { KEY_KBDILLUMUP }},
	{ KE_KEY,    0xb9, { KEY_KBDILLUMTOGGLE }},  /* NUC X15 actual Fn+F8 code */
	{ KE_KEY,    0xbb, { KEY_KBDILLUMTOGGLE }},
	{ KE_KEY,    0xb8, { KEY_FN_ESC }},

	{ KE_END }
};

/* ========================================================================== */

static struct input_dev *nuc_wmi_input_dev;

/* ========================================================================== */

static void toggle_fn_lock_from_event_handler(void)
{
	int status = nuc_wmi_fn_lock_get_state();

	if (status < 0)
		return;

	/* seemingly the returned status in the WMI event handler is not the current */
	pr_info("setting Fn lock state from %d to %d\n", !status, status);
	nuc_wmi_fn_lock_set_state(status);
}

#if IS_ENABLED(CONFIG_LEDS_BRIGHTNESS_HW_CHANGED)
extern struct rw_semaphore leds_list_lock;
extern struct list_head leds_list;

static void emit_keyboard_led_hw_changed(void)
{
	struct led_classdev *led;

	if (down_read_killable(&leds_list_lock))
		return;

	list_for_each_entry (led, &leds_list, node) {
		size_t name_length;
		const char *suffix;

		if (!(led->flags & LED_BRIGHT_HW_CHANGED))
			continue;

		name_length = strlen(led->name);

		if (name_length < strlen(KBD_BL_LED_SUFFIX))
			continue;

		suffix = led->name + name_length - strlen(KBD_BL_LED_SUFFIX);

		if (strcmp(suffix, KBD_BL_LED_SUFFIX) == 0) {
			if (mutex_lock_interruptible(&led->led_access))
				break;

			if (led_update_brightness(led) >= 0)
				led_classdev_notify_brightness_hw_changed(led, led->brightness);

			mutex_unlock(&led->led_access);
			break;
		}
	}

	up_read(&leds_list_lock);
}
#else
static inline void emit_keyboard_led_hw_changed(void)
{ }
#endif

static void process_event_72(const union acpi_object *obj)
{
	bool do_report = true;

	if (obj->type != ACPI_TYPE_INTEGER)
		return;

	switch (obj->integer.value) {
	/* caps lock */
	case 1:
		pr_info("caps lock\n");
		break;

	/* num lock */
	case 2:
		pr_info("num lock\n");
		break;

	/* scroll lock */
	case 3:
		pr_info("scroll lock\n");
		break;

	/* touchpad off (event 4 = firmware disabled touchpad) */
	case 4:
		pr_info("touchpad off\n");
		/* Don't write EC CTRL_4 — keep digitizer active for double-tap detection.
		 * The daemon handles actual disable via GNOME send-events. */
		break;

	/* touchpad on (event 5 = firmware enabled touchpad) */
	case 5:
		pr_info("touchpad on\n");
		break;

	/* mic mute — handled by userspace daemon (kbd_brightness_daemon).
	 * Do NOT report to the input subsystem: that would trigger GNOME's
	 * own mic-mute OSD/action and double-handle the event. */
	case 7:
		pr_info("mic mute\n");
		do_report = false;
		break;

	/* increase screen brightness */
	case 20:
		pr_info("increase screen brightness\n");
		/* do_report = !acpi_video_handles_brightness_key_presses() */
		break;

	/* decrease screen brightness */
	case 21:
		pr_info("decrease screen brightness\n");
		/* do_report = !acpi_video_handles_brightness_key_presses() */
		break;

	/* radio on */
	case 26:
		/* triggered in automatic mode when the rfkill hotkey is pressed */
		pr_info("radio on\n");
		break;

	/* radio off */
	case 27:
		/* triggered in automatic mode when the rfkill hotkey is pressed */
		pr_info("radio off\n");
		break;

	/* mute/unmute */
	case 53:
		pr_info("toggle mute\n");
		break;

	/* decrease volume */
	case 54:
		pr_info("decrease volume\n");
		break;

	/* increase volume */
	case 55:
		pr_info("increase volume\n");
		break;

	case 57:
		pr_info("lightbar on\n");
		break;

	case 58:
		pr_info("lightbar off\n");
		break;

	/* enable super key (win key) lock */
	case 64:
		pr_info("enable super key lock\n");
		break;

	/* decrease volume */
	case 65:
		pr_info("disable super key lock\n");
		break;

	/* enable/disable airplane mode */
	case 164:
		pr_info("toggle airplane mode\n");
		break;

	/* super key (win key) lock state changed */
	case 165:
		pr_info("super key lock state changed\n");
		sysfs_notify(&nuc_wmi_platform_dev->dev.kobj, NULL, "super_key_lock");
		break;

	case 166:
		pr_info("lightbar state changed\n");
		break;

	/* fan boost state changed */
	case 167:
		pr_info("fan boost state changed\n");
		break;

	/* charger unplugged/plugged in */
	case 171:
		pr_info("AC plugged/unplugged\n");
		break;

	/* perf mode button pressed */
	case 176:
		pr_info("change perf mode\n");
		nuc_wmi_cycle_perf_profile();
		/* sysfs_notify is done by the deferred work after EC readback */
		break;

	/* increase keyboard backlight */
	case 177:
		pr_info("keyboard backlight decrease\n");
		/* TODO: should it be handled here? */
		break;

	/* decrease keyboard backlight */
	case 178:
		pr_info("keyboard backlight increase\n");
		/* TODO: should it be handled here? */
		break;

	/* toggle Fn lock (Fn+ESC)*/
	case 184:
		pr_info("toggle Fn lock\n");
		toggle_fn_lock_from_event_handler();
		sysfs_notify(&nuc_wmi_platform_dev->dev.kobj, NULL, "fn_lock");
		break;

	/* keyboard backlight brightness changed */
	case 240:
		if (time_before(jiffies, wmi_handler_installed_at + WMI_GRACE_JIFFIES)) {
			pr_info("keyboard backlight changed (suppressed — grace period)\n");
			do_report = false;
			break;
		}
		pr_info("keyboard backlight changed\n");
		emit_keyboard_led_hw_changed();
		break;

	/* keyboard backlight toggle (Fn+F8) — alternate codes on NUC X15 */
	case 185:
	case 187:
		if (time_before(jiffies, wmi_handler_installed_at + WMI_GRACE_JIFFIES)) {
			pr_info("keyboard backlight changed (suppressed — grace period)\n");
			do_report = false;
			break;
		}
		pr_info("keyboard backlight changed\n");
		emit_keyboard_led_hw_changed();
		break;

	/* mic mute (alternate code on NUC X15) — same as case 7: suppress kernel report */
	case 183:
		pr_info("mic mute\n");
		do_report = false;
		break;

	default:
		pr_warn("unknown code: %u\n", (unsigned int) obj->integer.value);
		break;
	}

	if (do_report && nuc_wmi_input_dev)
		sparse_keymap_report_event(nuc_wmi_input_dev,
					   obj->integer.value, 1, true);

}

static void process_event(const union acpi_object *obj, const char *guid)
{
	pr_info("guid=%s obj=%p\n", guid, obj);

	if (!obj)
		return;

	pr_info("obj->type = %d\n", (int) obj->type);
	if (obj->type == ACPI_TYPE_INTEGER) {
		pr_info("int = %u\n", (unsigned int) obj->integer.value);
	} else if (obj->type == ACPI_TYPE_STRING) {
		pr_info("string = '%s'\n", obj->string.pointer);
	} else if (obj->type == ACPI_TYPE_BUFFER) {
		pr_info("buffer = %u %*ph", obj->buffer.length,
			(int) obj->buffer.length, (void *) obj->buffer.pointer);
	}

	if (strcmp(guid, NUC_WMI_EVENT_72_GUID) == 0)
		process_event_72(obj);
}

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 12, 0)
static void nuc_wmi_wmi_event_handler(union acpi_object *obj, void *context)
{
	process_event(obj, context);
}
#else
static void nuc_wmi_wmi_event_handler(u32 value, void *context)
{
	struct acpi_buffer response = { ACPI_ALLOCATE_BUFFER, NULL };
	acpi_status status;

	status = wmi_get_event_data(value, &response);
	if (ACPI_FAILURE(status)) {
		pr_err("bad WMI event status: %#010x\n", (unsigned int) status);
		return;
	}

	process_event(response.pointer, context);
	kfree(response.pointer);
}
#endif

static u8 uniwill_touchp_toggle_seq[] = {
	0xe0, 0x5b, // Super down
	0x1d,       // Control down
	0x76,       // Zenkaku/Hankaku down
	0xf6,       // Zenkaku/Hankaku up
	0x9d,       // Control up
	0xe0, 0xdb  // Super up
};

/* Kernel-level debounce: ignore re-fires within 3 seconds */
static ktime_t last_touchpad_toggle_time;

static void key_event_work(struct work_struct *work)
{
        ktime_t now = ktime_get();
        s64 elapsed_ms = ktime_to_ms(ktime_sub(now, last_touchpad_toggle_time));

        if (elapsed_ms < 3000) {
                pr_debug("touchpad toggle debounced (%lldms < 3000ms)\n", elapsed_ms);
                return;
        }
        last_touchpad_toggle_time = now;

        pr_info("touchpad toggle pressed\n");
        /* Report KEY_F21 so GNOME shows native touchpad OSD.
         * Our daemon overrides GNOME's send-events via gsettings. */
        if (nuc_wmi_input_dev)
                sparse_keymap_report_event(nuc_wmi_input_dev, 0x04, 1, true);
}
static DECLARE_WORK(uniwill_key_event_work, key_event_work);

#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 14, 0)
static bool uniwill_i8042_filter(unsigned char data, unsigned char str,
				 struct serio *port)
#else
static bool uniwill_i8042_filter(unsigned char data, unsigned char str,
				 struct serio *port, void *context)
#endif
{
	static u8 seq_pos = 0;

	if (unlikely(data == uniwill_touchp_toggle_seq[seq_pos])) {
		++seq_pos;
		if (unlikely(data == 0x76 || data == 0xf6))
			return true;
		else if (unlikely(seq_pos == ARRAY_SIZE(uniwill_touchp_toggle_seq))) {
			schedule_work(&uniwill_key_event_work);
			seq_pos = 0;
		}
		return false;
	}

	seq_pos = 0;
	if (unlikely(data == uniwill_touchp_toggle_seq[seq_pos])) {
		++seq_pos;
		return false;
	}

	return false;
}

static int __init setup_input_dev(void)
{
	int err = 0;


	nuc_wmi_input_dev = input_allocate_device();
	if (!nuc_wmi_input_dev)
		return -ENOMEM;

	nuc_wmi_input_dev->name = "NUC WMI input device";
	nuc_wmi_input_dev->phys = "nuc_wmi_laptop/input0";
	nuc_wmi_input_dev->id.bustype = BUS_HOST;
	nuc_wmi_input_dev->id.vendor  = 0x8086; /* Intel */
	nuc_wmi_input_dev->id.product = 0x0F15; /* NUC X15 */
	nuc_wmi_input_dev->dev.parent = &nuc_wmi_platform_dev->dev;

	err = sparse_keymap_setup(nuc_wmi_input_dev, nuc_wmi_wmi_hotkeys, NULL);
	if (err)
		goto err_free_device;

	err = nuc_wmi_rfkill_get_wifi_state();
	if (err >= 0)
		input_report_switch(nuc_wmi_input_dev, SW_RFKILL_ALL, err);
	else
		input_report_switch(nuc_wmi_input_dev, SW_RFKILL_ALL, 1);

	err = input_register_device(nuc_wmi_input_dev);
	if (err)
		goto err_free_device;

	return err;

err_free_device:
	input_free_device(nuc_wmi_input_dev);
	nuc_wmi_input_dev = NULL;

	return err;
}

/* ========================================================================== */

int __init nuc_wmi_wmi_events_setup(void)
{
	int err = 0, i;

	(void) setup_input_dev();

#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 14, 0)
	i8042_install_filter(uniwill_i8042_filter);
#else
	i8042_install_filter(uniwill_i8042_filter, NULL);
#endif

	for (i = 0; i < ARRAY_SIZE(nuc_wmi_wmi_event_guids); i++) {
		const char *guid = nuc_wmi_wmi_event_guids[i].guid;
		acpi_status status =
			wmi_install_notify_handler(guid, nuc_wmi_wmi_event_handler, (void *) guid);

		if (ACPI_FAILURE(status)) {
			pr_warn("could not install WMI notify handler for '%s': [%#010lx] %s\n",
				guid, (unsigned long) status, acpi_format_exception(status));
		} else {
			nuc_wmi_wmi_event_guids[i].handler_installed = true;
		}
	}

	wmi_handler_installed_at = jiffies;

	return err;
}

void nuc_wmi_wmi_events_cleanup(void)
{
	int i;

	for (i = 0; i < ARRAY_SIZE(nuc_wmi_wmi_event_guids); i++) {
		if (nuc_wmi_wmi_event_guids[i].handler_installed) {
			wmi_remove_notify_handler(nuc_wmi_wmi_event_guids[i].guid);
			nuc_wmi_wmi_event_guids[i].handler_installed = false;
		}
	}

#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 14, 0)
	i8042_remove_filter(uniwill_i8042_filter);
#else
	i8042_remove_filter(uniwill_i8042_filter);
#endif

	if (nuc_wmi_input_dev)
		input_unregister_device(nuc_wmi_input_dev);
}
