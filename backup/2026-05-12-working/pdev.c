// SPDX-License-Identifier: GPL-2.0
#include "pr.h"

#include <linux/bug.h>
#include <linux/delay.h>
#include <linux/workqueue.h>
#include <linux/device.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/platform_device.h>

#include "util.h"
#include "ec.h"
#include "features.h"
#include "misc.h"
#include "pdev.h"

/* ========================================================================== */

struct platform_device *nuc_wmi_platform_dev;

/* ========================================================================== */

static ssize_t fan_reduced_duty_cycle_show(struct device *dev,
					   struct device_attribute *attr, char *buf)
{
	int status = ec_read_byte(BIOS_CTRL_3_ADDR);

	if (status < 0)
		return status;

	return sprintf(buf, "%d\n", !!(status & BIOS_CTRL_3_FAN_REDUCED_DUTY_CYCLE));
}

static ssize_t fan_reduced_duty_cycle_store(struct device *dev, struct device_attribute *attr,
					    const char *buf, size_t count)
{
	int status;
	bool value;

	if (kstrtobool(buf, &value))
		return -EINVAL;

	status = ec_read_byte(BIOS_CTRL_3_ADDR);
	if (status < 0)
		return status;

	status = SET_BIT(status, BIOS_CTRL_3_FAN_REDUCED_DUTY_CYCLE, value);

	status = ec_write_byte(BIOS_CTRL_3_ADDR, status);

	if (status < 0)
		return status;

	return count;
}

static ssize_t fan_always_on_show(struct device *dev,
				  struct device_attribute *attr, char *buf)
{
	int status = ec_read_byte(BIOS_CTRL_3_ADDR);

	if (status < 0)
		return status;

	return sprintf(buf, "%d\n", !!(status & BIOS_CTRL_3_FAN_ALWAYS_ON));
}

static ssize_t fan_always_on_store(struct device *dev, struct device_attribute *attr,
				   const char *buf, size_t count)
{
	int status;
	bool value;

	if (kstrtobool(buf, &value))
		return -EINVAL;

	status = ec_read_byte(BIOS_CTRL_3_ADDR);
	if (status < 0)
		return status;

	status = SET_BIT(status, BIOS_CTRL_3_FAN_ALWAYS_ON, value);

	status = ec_write_byte(BIOS_CTRL_3_ADDR, status);

	if (status < 0)
		return status;

	return count;
}

static ssize_t fn_lock_show(struct device *dev,
			    struct device_attribute *attr, char *buf)
{
	int status = nuc_wmi_fn_lock_get_state();

	if (status < 0)
		return status;

	return sprintf(buf, "%d\n", status);
}

static ssize_t fn_lock_store(struct device *dev, struct device_attribute *attr,
			     const char *buf, size_t count)
{
	int status;
	bool value;

	if (kstrtobool(buf, &value))
		return -EINVAL;

	status = nuc_wmi_fn_lock_set_state(value);
	if (status < 0)
		return status;

	return count;
}

static ssize_t fn_lock_switch_show(struct device *dev,
				   struct device_attribute *attr, char *buf)
{
	int status = ec_read_byte(AP_BIOS_BYTE_ADDR);

	if (status < 0)
		return status;

	return sprintf(buf, "%d\n", !!(status & AP_BIOS_BYTE_FN_LOCK_SWITCH));
}

static ssize_t fn_lock_switch_store(struct device *dev, struct device_attribute *attr,
				    const char *buf, size_t count)
{
	int status;
	bool value;

	if (kstrtobool(buf, &value))
		return -EINVAL;

	status = ec_read_byte(AP_BIOS_BYTE_ADDR);
	if (status < 0)
		return status;

	status = SET_BIT(status, AP_BIOS_BYTE_FN_LOCK_SWITCH, value);

	status = ec_write_byte(AP_BIOS_BYTE_ADDR, status);

	if (status < 0)
		return status;

	return count;
}

static ssize_t manual_control_show(struct device *dev,
				   struct device_attribute *attr, char *buf)
{
	int status = ec_read_byte(CTRL_1_ADDR);

	if (status < 0)
		return status;

	return sprintf(buf, "%d\n", !!(status & CTRL_1_MANUAL_MODE));
}

static ssize_t manual_control_store(struct device *dev, struct device_attribute *attr,
				    const char *buf, size_t count)
{
	int status;
	bool value;

	if (kstrtobool(buf, &value))
		return -EINVAL;

	status = ec_read_byte(CTRL_1_ADDR);
	if (status < 0)
		return status;

	status = SET_BIT(status, CTRL_1_MANUAL_MODE, value);

	status = ec_write_byte(CTRL_1_ADDR, status);

	if (status < 0)
		return status;

	return count;
}

static ssize_t super_key_lock_show(struct device *dev,
				   struct device_attribute *attr, char *buf)
{
	int status = ec_read_byte(STATUS_1_ADDR);

	if (status < 0)
		return status;

	return sprintf(buf, "%d\n", !!(status & STATUS_1_SUPER_KEY_LOCK));
}

static ssize_t super_key_lock_store(struct device *dev, struct device_attribute *attr,
				    const char *buf, size_t count)
{
	int status;
	bool value;

	if (kstrtobool(buf, &value))
		return -EINVAL;

	status = ec_read_byte(STATUS_1_ADDR);
	if (status < 0)
		return status;

	if (value != !!(status & STATUS_1_SUPER_KEY_LOCK)) {
		status = ec_write_byte(TRIGGER_1_ADDR, TRIGGER_1_SUPER_KEY_LOCK);

		if (status < 0)
			return status;
	}

	return count;
}

/* ========================================================================== */
/* Charging Profile Attributes (Ported from tuxedo-keyboard) */
/* ========================================================================== */

static ssize_t charging_profile_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	int err;
	u8 val;

	err = ec_read_byte(0x07a6);
	if (err < 0) return err;

	val = (err >> 4) & 0x03;
	if (val == 0x00) return sprintf(buf, "high_capacity\n");
	if (val == 0x01) return sprintf(buf, "balanced\n");
	if (val == 0x02) return sprintf(buf, "stationary\n");

	return sprintf(buf, "unknown\n");
}

static ssize_t charging_profile_store(struct device *dev, struct device_attribute *attr,
				    const char *buf, size_t count)
{
	int err;
	u8 val, current_data;

	if (sysfs_streq(buf, "high_capacity")) val = 0x00;
	else if (sysfs_streq(buf, "balanced")) val = 0x01;
	else if (sysfs_streq(buf, "stationary")) val = 0x02;
	else return -EINVAL;

	err = ec_read_byte(0x07a6);
	if (err < 0) return err;

	current_data = err;
	current_data = (current_data & ~(0x03 << 4)) | (val << 4);

	err = ec_write_byte(0x07a6, current_data);
	if (err < 0) return err;

	return count;
}

/* ========================================================================== */
/* Performance Profile
 * EC register 0x0751 controls the thermal profile AND the button LEDs.
 * Tuxedo reference proves the bitmask scheme:
 *   Bits 4, 5, 7 of 0x0751 (mask 0xb0):
 *     Silent (0):      0xa0 (bits 7+5 set)
 *     Balanced (1):    0x00 (bits cleared)
 *     Performance (2): 0x10 (bit 4 set)
 *   Benchmark (3) is app-only (not written to EC, handled by manual PWM).
 * The physical button cycles: Silent(0) -> Balanced(1) -> Performance(2) -> Silent(0)
 */
/* ========================================================================== */

#define PERF_PROFILE_ADDR  ADDR(0x07, 0x51)
#define PERF_PROFILE_MASK  0xb0

static const uint8_t perf_profile_bits[] = {
	[0] = 0xa0,  /* Silent */
	[1] = 0x00,  /* Balanced */
	[2] = 0x10,  /* Performance */
};

static int current_benchmark_mode = 0; /* 1 if app set benchmark (3) */
static int current_sw_profile = 1;     /* Software-tracked profile: 0=Silent, 1=Balanced, 2=Performance */


/*
 * Map CTRL_3 power LED bits to profile index.
 * CTRL_3 (0x07A5) bits 0-1 reflect the actual button LED state and
 * are readable at any time, even with manual mode ON — unlike 0x0751
 * which gives stale/corrupted reads.
 */
static const uint8_t ctrl3_led_to_profile[] = {
	[CTRL_3_PWR_LED_LEFT & 0x03] = 1,  /* 0x00 = 1 LED  = Balanced */
	[CTRL_3_PWR_LED_BOTH & 0x03] = 2,  /* 0x01 = 2 LEDs = Performance */
	[CTRL_3_PWR_LED_NONE & 0x03] = 0,  /* 0x02 = 0 LEDs = Silent */
	[0x03]                        = 1,  /* fallback */
};

static int nuc_wmi_read_perf_profile_from_ec(void)
{
	int val;

	if (current_benchmark_mode)
		return 3;

	/*
	 * Read the actual profile from CTRL_3 power LED register.
	 * This is always reliable regardless of manual mode state.
	 */
	val = ec_read_byte(CTRL_3_ADDR);
	if (val >= 0) {
		current_sw_profile = ctrl3_led_to_profile[val & CTRL_3_PWR_LED_MASK];
		return current_sw_profile;
	}

	return current_sw_profile;
}

static int nuc_wmi_write_perf_profile_to_ec(int profile)
{
	int ctrl1, err;

	if (profile == 3) {
		/* Benchmark: set EC to balanced, app handles fans */
		current_benchmark_mode = 1;
		current_sw_profile = 1;
		profile = 1;
	} else {
		current_benchmark_mode = 0;
		current_sw_profile = profile;
	}

	if (profile < 0 || profile > 2)
		return -EINVAL;

	/* Clear manual mode bit (bit 0 only) so EC accepts profile write
	 * and updates the button LEDs. We do NOT restore manual mode here —
	 * the fan-curve daemon will re-enable it on its next tick (~1s).
	 * This gives the EC time to process the profile change and update LEDs. */
	ctrl1 = ec_read_byte(CTRL_1_ADDR);
	if (ctrl1 >= 0 && (ctrl1 & CTRL_1_MANUAL_MODE))
		ec_write_byte(CTRL_1_ADDR, ctrl1 & ~CTRL_1_MANUAL_MODE);

	/*
	 * Write profile bits. Observed EC values:
	 *   Silent(0)      = 0xa0 (bits 7+5)
	 *   Balanced(1)    = 0x00 (cleared)
	 *   Performance(2) = 0x10 (bit 4)
	 */
	err = ec_write_byte(PERF_PROFILE_ADDR, perf_profile_bits[profile]);


	return err;
}

int nuc_wmi_get_perf_profile(void)
{
	return nuc_wmi_read_perf_profile_from_ec();
}

/*
 * Deferred work: clear manual mode so the EC can update button LEDs,
 * then notify userspace.  The fan daemon re-enables manual mode
 * after its ~2s grace period.
 *
 * We do NOT read any register here — nuc_wmi_read_perf_profile_from_ec()
 * reads CTRL_3 on demand, which is always reliable.
 */
static void perf_profile_deferred_led_update(struct work_struct *work)
{
	int ctrl1;

	ctrl1 = ec_read_byte(CTRL_1_ADDR);
	if (ctrl1 >= 0 && (ctrl1 & CTRL_1_MANUAL_MODE))
		ec_write_byte(CTRL_1_ADDR, ctrl1 & ~CTRL_1_MANUAL_MODE);

	sysfs_notify(&nuc_wmi_platform_dev->dev.kobj, NULL, "pm_profile");
}
static DECLARE_DELAYED_WORK(perf_profile_work, perf_profile_deferred_led_update);

void nuc_wmi_cycle_perf_profile(void)
{
	/* In benchmark mode, ignore the physical button entirely */
	if (current_benchmark_mode)
		return;

	/* Cancel any pending work */
	cancel_delayed_work(&perf_profile_work);

	/*
	 * Don't touch any EC registers here — that causes double-cycling.
	 * Don't track in software — that drifts out of sync.
	 *
	 * Instead: schedule deferred manual-mode-clear (300ms) so the EC
	 * updates the button LEDs.  The actual profile is always read from
	 * CTRL_3 (0x07A5) on demand — see nuc_wmi_read_perf_profile_from_ec().
	 */
	schedule_delayed_work(&perf_profile_work, msecs_to_jiffies(300));
}

/* Debug: read multiple EC registers to find where the profile button state is stored */
static ssize_t debug_ec_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	int i, val, len = 0;
	/* Scan wider range of EC registers in page 0x07 */
	for (i = 0x40; i <= 0xAF; i++) {
		val = ec_read_byte(ADDR(0x07, i));
		if (val >= 0)
			len += sprintf(buf + len, "%02x=%02x ", i, val);
		if ((i & 0x0F) == 0x0F)
			len += sprintf(buf + len, "\n");
	}
	return len;
}

static ssize_t debug_ec_store(struct device *dev, struct device_attribute *attr,
			      const char *buf, size_t count)
{
	unsigned int offset, value;

	if (sscanf(buf, "%x %x", &offset, &value) != 2)
		return -EINVAL;

	if (offset > 0xFF || value > 0xFF)
		return -EINVAL;

	ec_write_byte(ADDR(0x07, offset), value);
	return count;
}
static DEVICE_ATTR_RW(debug_ec);

/* ========================================================================== */
/* Touchpad state from EC CTRL_4 register bit 6 */
/* ========================================================================== */

static ssize_t touchpad_enabled_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	int status = ec_read_byte(CTRL_4_ADDR);
	if (status < 0)
		return status;
	/* Bit 6 set = touchpad OFF, so invert */
	return sprintf(buf, "%d\n", !(status & CTRL_4_TOUCHPAD_TOGGLE_OFF));
}

static ssize_t touchpad_enabled_store(struct device *dev, struct device_attribute *attr,
				      const char *buf, size_t count)
{
	int status;
	bool value;

	if (kstrtobool(buf, &value))
		return -EINVAL;

	status = ec_read_byte(CTRL_4_ADDR);
	if (status < 0)
		return status;

	if (value)
		status &= ~CTRL_4_TOUCHPAD_TOGGLE_OFF;
	else
		status |= CTRL_4_TOUCHPAD_TOGGLE_OFF;

	status = ec_write_byte(CTRL_4_ADDR, status);
	if (status < 0)
		return status;

	return count;
}
static DEVICE_ATTR_RW(touchpad_enabled);

/* ========================================================================== */
/* Performance Profile - tracked in software via WMI event 176.
 * The EC does NOT expose the current profile in any readable register.
 * Button LEDs: both on=Performance(2), one on=Balanced(1), both off=Silent(0)
 * Cycle order: Balanced(1) -> Performance(2) -> Silent(0) -> Balanced(1)
 */
/* ========================================================================== */

static ssize_t pm_profile_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	return sprintf(buf, "%d\n", nuc_wmi_read_perf_profile_from_ec());
}

static ssize_t pm_profile_store(struct device *dev, struct device_attribute *attr,
			       const char *buf, size_t count)
{
	unsigned int val;
	int err;

	if (kstrtouint(buf, 10, &val) || val > 3)
		return -EINVAL;

	err = nuc_wmi_write_perf_profile_to_ec(val);
	if (err < 0)
		return err;

	return count;
}

/* ========================================================================== */

static DEVICE_ATTR_RW(fn_lock);
static DEVICE_ATTR_RW(fn_lock_switch);
static DEVICE_ATTR_RW(fan_always_on);
static DEVICE_ATTR_RW(fan_reduced_duty_cycle);
static DEVICE_ATTR_RW(manual_control);
static DEVICE_ATTR_RW(super_key_lock);
static DEVICE_ATTR_RW(charging_profile);
static DEVICE_ATTR_RW(pm_profile);

static struct attribute *nuc_wmi_laptop_attrs[] = {
	&dev_attr_fn_lock.attr,
	&dev_attr_fn_lock_switch.attr,
	&dev_attr_fan_always_on.attr,
	&dev_attr_fan_reduced_duty_cycle.attr,
	&dev_attr_manual_control.attr,
	&dev_attr_super_key_lock.attr,
	&dev_attr_charging_profile.attr,
	&dev_attr_pm_profile.attr,
	&dev_attr_debug_ec.attr,
	&dev_attr_touchpad_enabled.attr,
	NULL
};

/* ========================================================================== */

static umode_t nuc_wmi_laptop_attr_is_visible(struct kobject *kobj, struct attribute *attr, int n)
{
	bool ok = false;

	if (attr == &dev_attr_fn_lock.attr || attr == &dev_attr_fn_lock_switch.attr)
		ok = nuc_wmi_features.fn_lock;
	else if (attr == &dev_attr_fan_always_on.attr || attr == &dev_attr_fan_reduced_duty_cycle.attr)
		ok = nuc_wmi_features.fan_extras;
	else if (attr == &dev_attr_manual_control.attr)
		ok = true;
	else if (attr == &dev_attr_super_key_lock.attr)
		ok = true;
	else if (attr == &dev_attr_charging_profile.attr)
		ok = true; // Expose on all for now
	else if (attr == &dev_attr_pm_profile.attr)
		ok = true;
	else if (attr == &dev_attr_debug_ec.attr)
		ok = true;
	else if (attr == &dev_attr_touchpad_enabled.attr)
		ok = true;

	return ok ? attr->mode : 0;
}

/* ========================================================================== */

static const struct attribute_group nuc_wmi_laptop_group = {
	.is_visible = nuc_wmi_laptop_attr_is_visible,
	.attrs = nuc_wmi_laptop_attrs,
};

static const struct attribute_group *nuc_wmi_laptop_groups[] = {
	&nuc_wmi_laptop_group,
	NULL
};

/* ========================================================================== */

int __init nuc_wmi_pdev_setup(void)
{
	int err, val;

	/* Read initial performance profile from CTRL_3 power LED register.
	 * CTRL_3 bits 0-1 reliably reflect the actual profile at all times. */
	{
		val = ec_read_byte(CTRL_3_ADDR);
		if (val >= 0) {
			current_sw_profile = ctrl3_led_to_profile[val & CTRL_3_PWR_LED_MASK];
			pr_info("nuc_wmi: initial perf profile = %d (CTRL_3 = 0x%02x)\n",
				current_sw_profile, val);
		}
	}

	nuc_wmi_platform_dev = platform_device_alloc(KBUILD_MODNAME, PLATFORM_DEVID_NONE);
	if (!nuc_wmi_platform_dev)
		return -ENOMEM;

	nuc_wmi_platform_dev->dev.groups = nuc_wmi_laptop_groups;

	err = platform_device_add(nuc_wmi_platform_dev);
	if (err) {
		platform_device_put(nuc_wmi_platform_dev);
		nuc_wmi_platform_dev = NULL;
	}

	return err;
}

void nuc_wmi_pdev_cleanup(void)
{
	cancel_delayed_work_sync(&perf_profile_work);
	/* checks for IS_ERR_OR_NULL() */
	platform_device_unregister(nuc_wmi_platform_dev);
}
