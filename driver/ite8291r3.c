// SPDX-License-Identifier: GPL-2.0
/*
 * ITE8291R3 USB keyboard backlight driver
 *
 * Supports per-key RGB, effects, brightness control for ITE Tech 8291
 * revision 3 keyboard controllers found in Intel NUC X15 / TongFang laptops.
 *
 * Binds to USB interface 1 of VID 048D, PIDs 6004/6006/CE00.
 * Exposes sysfs under /sys/class/leds/ite8291r3::kbd_backlight/
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/usb.h>
#include <linux/leds.h>
#include <linux/slab.h>
#include <linux/mutex.h>

#define ITE8291R3_VENDOR_ID	0x048D

#define NUM_ROWS		6
#define NUM_COLS		21
#define ROW_BUFFER_LEN		(3 * NUM_COLS + 2)

#define ROW_RED_OFFSET		(1 + 2 * NUM_COLS)
#define ROW_GREEN_OFFSET	(1 + 1 * NUM_COLS)
#define ROW_BLUE_OFFSET		(1 + 0 * NUM_COLS)

/* Commands */
#define CMD_SET_PALETTE		0x14
#define CMD_SET_EFFECT		8
#define CMD_SET_BRIGHTNESS	9
#define CMD_SET_ROW_INDEX	22
#define CMD_GET_FW_VERSION	128
#define CMD_GET_EFFECT		136

struct ite8291r3_data {
	struct usb_device *udev;
	struct usb_interface *intf;
	struct led_classdev led_cdev;
	struct mutex lock;
	int ep_out;
	u8 brightness;
	u8 r, g, b;
	u8 effect;
	u8 speed;		/* effect speed 0-9 (default 5) */
	u8 color_index;		/* effect color index: 0-7=single, 8=random/multi (default 8) */
	u8 reactive;		/* reactive mode: 0=off, 1=on (keypress-triggered) */
	u8 direction;		/* wave direction: 0=none, 1=right, 2=left, 3=up, 4=down */
	u8 audio_mode;		/* audio mode: 0=normal, 1=audio sync, 2=direct, 3=diag, 4=bpm */
	u8 audio_sensitivity;	/* audio ADC gain/threshold: 0x00-0xFF (default 0x80) */
	u8 row_data[NUM_ROWS][ROW_BUFFER_LEN];
};

static int ite8291r3_send_ctrl(struct ite8291r3_data *data, u8 *payload, int len)
{
	struct usb_device *udev = data->udev;
	u8 *buf;
	int ret;

	buf = kmemdup(payload, 8, GFP_KERNEL);
	if (!buf)
		return -ENOMEM;

	ret = usb_control_msg(udev,
		usb_sndctrlpipe(udev, 0),
		0x09,	/* HID_REQ_SET_REPORT */
		0x21,	/* HOST_TO_DEVICE | CLASS | INTERFACE */
		0x0300,	/* Feature report, Report ID 0 */
		0x0001,	/* interface 1 */
		buf, 8, 1000);

	kfree(buf);
	return ret < 0 ? ret : 0;
}

/*
 * Send a command using Report ID 0xCC (for palette and other extended commands).
 * Payload is prepended with 0xCC and sent with wValue=0x03CC.
 */
static int ite8291r3_send_ctrl_cc(struct ite8291r3_data *data, u8 *payload, int len)
{
	struct usb_device *udev = data->udev;
	u8 *buf;
	int ret;
	int total = len + 1;  /* +1 for 0xCC prefix */

	if (total > 8)
		total = 8;

	buf = kzalloc(8, GFP_KERNEL);
	if (!buf)
		return -ENOMEM;

	buf[0] = 0xCC;
	memcpy(buf + 1, payload, total - 1);

	ret = usb_control_msg(udev,
		usb_sndctrlpipe(udev, 0),
		0x09,	/* HID_REQ_SET_REPORT */
		0x21,	/* HOST_TO_DEVICE | CLASS | INTERFACE */
		0x03CC,	/* Feature report, Report ID 0xCC */
		0x0001,	/* interface 1 */
		buf, 8, 1000);

	kfree(buf);
	return ret < 0 ? ret : 0;
}

static int ite8291r3_send_row(struct ite8291r3_data *data, int row)
{
	struct usb_device *udev = data->udev;
	u8 *buf;
	int ret, actual;

	buf = kmemdup(data->row_data[row], ROW_BUFFER_LEN, GFP_KERNEL);
	if (!buf)
		return -ENOMEM;

	ret = usb_interrupt_msg(udev,
		usb_sndintpipe(udev, data->ep_out),
		buf, ROW_BUFFER_LEN, &actual, 1000);

	kfree(buf);
	return ret;
}

static int ite8291r3_set_row_index(struct ite8291r3_data *data, int row)
{
	u8 cmd[8] = { CMD_SET_ROW_INDEX, 0x00, (u8)row, 0, 0, 0, 0, 0 };
	return ite8291r3_send_ctrl(data, cmd, 8);
}

static int ite8291r3_set_effect_raw(struct ite8291r3_data *data, u8 control,
		u8 effect, u8 speed, u8 brightness, u8 color, u8 dir, u8 save)
{
	u8 cmd[8] = { CMD_SET_EFFECT, control, effect, speed, brightness, color, dir, save };
	return ite8291r3_send_ctrl(data, cmd, 8);
}

/* Program a single palette slot (index 1-7) with an RGB color.
 * NOTE: Silently ignored on FW 16.04 (ROM-burned palette). Kept for sysfs and future FW.
 */
static int ite8291r3_set_palette(struct ite8291r3_data *data, u8 index, u8 r, u8 g, u8 b)
{
	u8 cmd[8] = { CMD_SET_PALETTE, index, r, g, b, 0, 0, 0 };
	return ite8291r3_send_ctrl(data, cmd, 8);
}

/* Palette LUT is ROM-burned on FW 16.04 — writes silently ignored */

/* Default palette kept for reference and potential future FW support */
static const u8 default_palette[][3] = {
	/* index 1 */ { 0xFF, 0x00, 0x00 },  /* red */
	/* index 2 */ { 0xFF, 0x80, 0x00 },  /* orange */
	/* index 3 */ { 0xFF, 0xFF, 0x00 },  /* yellow */
	/* index 4 */ { 0x00, 0xFF, 0x00 },  /* green */
	/* index 5 */ { 0x00, 0x00, 0xFF },  /* blue */
	/* index 6 */ { 0x00, 0xFF, 0xFF },  /* teal/cyan */
	/* index 7 */ { 0x80, 0x00, 0xFF },  /* purple */
};

static void ite8291r3_init_palette(struct ite8291r3_data *data)
{
	int i;
	for (i = 0; i < 7; i++)
		ite8291r3_set_palette(data, i + 1,
			default_palette[i][0], default_palette[i][1], default_palette[i][2]);
}

static int ite8291r3_enable_user_mode(struct ite8291r3_data *data, u8 brightness, u8 save)
{
	return ite8291r3_set_effect_raw(data, 0x02, 51, 0, brightness, 0, 0, save);
}

static int ite8291r3_set_brightness_hw(struct ite8291r3_data *data, u8 brightness)
{
	u8 cmd[8] = { CMD_SET_BRIGHTNESS, 0x02, brightness, 0, 0, 0, 0, 0 };
	return ite8291r3_send_ctrl(data, cmd, 8);
}

static int ite8291r3_turn_off(struct ite8291r3_data *data)
{
	return ite8291r3_set_effect_raw(data, 0x01, 0, 0, 0, 0, 0, 0);
}

static int ite8291r3_set_mono_color(struct ite8291r3_data *data, u8 r, u8 g, u8 b, u8 brightness, u8 save)
{
	int ret, row, i;

	ret = ite8291r3_enable_user_mode(data, brightness, save);
	if (ret)
		return ret;

	for (row = 0; row < NUM_ROWS; row++) {
		memset(data->row_data[row], 0, ROW_BUFFER_LEN);
		for (i = 0; i < NUM_COLS; i++) {
			data->row_data[row][ROW_RED_OFFSET + i] = r;
			data->row_data[row][ROW_GREEN_OFFSET + i] = g;
			data->row_data[row][ROW_BLUE_OFFSET + i] = b;
		}
		ret = ite8291r3_set_row_index(data, row);
		if (ret) return ret;
		ret = ite8291r3_send_row(data, row);
		if (ret) return ret;
	}
	return 0;
}

/* --- LED class --- */

/*
 * ite8291r3_led_set — LED core brightness_set callback.
 *
 * Per-key mode (effect 0xFF) special case:
 *   CMD_SET_BRIGHTNESS (0x09) forces the chip's state machine back to its
 *   firmware animation engine, destroying the per-key framebuffer.  Instead
 *   we implement brightness as *software RGB scaling*: scale each stored RGB
 *   byte by the new brightness factor and re-push all 6 rows.  Hardware
 *   brightness stays fixed at maximum so CMD 0x09 is never sent while per-key
 *   mode is active.
 *
 * All other effects use the hardware brightness command as before.
 */
static void ite8291r3_led_set(struct led_classdev *cdev, enum led_brightness brightness)
{
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	u8 new_bri = brightness * 50 / 255;
	int i, col;

	mutex_lock(&data->lock);
	data->brightness = new_bri;

	if (brightness == 0) {
		ite8291r3_turn_off(data);
		mutex_unlock(&data->lock);
		return;
	}

	if (data->effect == 0xFF) {
		/*
		 * Per-key mode: scale stored (full-brightness) row_data by the
		 * new brightness factor and re-push all rows.  row_data always
		 * stores the full-intensity colours so repeated scaling does not
		 * degrade precision.
		 *
		 * Factor = new_bri / 50  (new_bri is 0-50, 50 = 100 %)
		 * Floor at 1 for non-zero source bytes so coloured keys stay
		 * visible even at very low brightness.
		 */
		u8 scaled[NUM_ROWS][ROW_BUFFER_LEN];
		memcpy(scaled, data->row_data, sizeof(scaled));

		for (i = 0; i < NUM_ROWS; i++) {
			for (col = 0; col < NUM_COLS; col++) {
				u8 rv = data->row_data[i][ROW_RED_OFFSET   + col];
				u8 gv = data->row_data[i][ROW_GREEN_OFFSET + col];
				u8 bv = data->row_data[i][ROW_BLUE_OFFSET  + col];

				scaled[i][ROW_RED_OFFSET   + col] = rv ? max(1u, (unsigned)(rv * new_bri / 50)) : 0;
				scaled[i][ROW_GREEN_OFFSET + col] = gv ? max(1u, (unsigned)(gv * new_bri / 50)) : 0;
				scaled[i][ROW_BLUE_OFFSET  + col] = bv ? max(1u, (unsigned)(bv * new_bri / 50)) : 0;
			}
		}

		/* Re-enter user/direct mode then push scaled rows */
		ite8291r3_enable_user_mode(data, 50, 0); /* hardware brightness = max; no flash write */
		usleep_range(14000, 16000);
		for (i = 0; i < NUM_ROWS; i++) {
			u8 saved[ROW_BUFFER_LEN];
			memcpy(saved, data->row_data[i], ROW_BUFFER_LEN);
			memcpy(data->row_data[i], scaled[i], ROW_BUFFER_LEN);
			ite8291r3_set_row_index(data, i);
			ite8291r3_send_row(data, i);
			memcpy(data->row_data[i], saved, ROW_BUFFER_LEN);
		}
		/* Latch: second enable_user_mode copies staging → active matrix */
		usleep_range(14000, 16000);
		ite8291r3_enable_user_mode(data, 50, 0);
	} else {
		ite8291r3_set_brightness_hw(data, new_bri);
	}

	mutex_unlock(&data->lock);
}

static enum led_brightness ite8291r3_led_get(struct led_classdev *cdev)
{
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	return data->brightness * 255 / 50;
}

/* --- sysfs --- */

static ssize_t color_store(struct device *dev, struct device_attribute *attr,
			   const char *buf, size_t count)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	unsigned int r, g, b;

	if (sscanf(buf, "%u %u %u", &r, &g, &b) != 3)
		return -EINVAL;
	if (r > 255 || g > 255 || b > 255)
		return -EINVAL;

	mutex_lock(&data->lock);
	data->r = r; data->g = g; data->b = b;
	ite8291r3_set_mono_color(data, r, g, b, data->brightness, 1);
	mutex_unlock(&data->lock);
	return count;
}

static ssize_t color_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	return sysfs_emit(buf, "%u %u %u\n", data->r, data->g, data->b);
}
static DEVICE_ATTR_RW(color);

static ssize_t effect_store(struct device *dev, struct device_attribute *attr,
			    const char *buf, size_t count)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	u8 eff = 0;

	if (sysfs_streq(buf, "off")) {
		mutex_lock(&data->lock);
		ite8291r3_turn_off(data);
		data->effect = 0;
		mutex_unlock(&data->lock);
		return count;
	} else if (sysfs_streq(buf, "breathing")) { eff = 0x02; }
	else if (sysfs_streq(buf, "wave"))       { eff = 0x03; }
	else if (sysfs_streq(buf, "random"))     { eff = 0x04; }
	else if (sysfs_streq(buf, "rainbow"))    { eff = 0x05; }
	else if (sysfs_streq(buf, "ripple"))     { eff = 0x06; }
	else if (sysfs_streq(buf, "marquee"))    { eff = 0x09; }
	else if (sysfs_streq(buf, "raindrop"))   { eff = 0x0A; }
	else if (sysfs_streq(buf, "aurora"))     { eff = 0x0E; }
	else if (sysfs_streq(buf, "fireworks"))  { eff = 0x11; }
	else if (sysfs_streq(buf, "reactive"))   { eff = 0x0B; }
	else if (sysfs_streq(buf, "monocolor")) {
		mutex_lock(&data->lock);
		ite8291r3_set_mono_color(data, data->r, data->g, data->b, data->brightness, 1);
		data->effect = 51;
		mutex_unlock(&data->lock);
		return count;
	} else {
		return -EINVAL;
	}

	mutex_lock(&data->lock);
	data->effect = eff;
	{
		/* byte 6: for wave (0x03) = direction, for reactive effects = reactive flag */
		u8 byte6 = (eff == 0x03) ? data->direction : data->reactive;
		ite8291r3_set_effect_raw(data, 0x02, eff, data->speed, data->brightness, data->color_index, byte6, 1);
	}
	/* Send audio mode command (CMD 0x02) if enabled */
	if (data->audio_mode > 0) {
		u8 audio_cmd[8] = { 0x02, data->audio_mode, data->audio_sensitivity, 0, 0, 0, 0, 0 };
		ite8291r3_send_ctrl(data, audio_cmd, 8);
	}
	mutex_unlock(&data->lock);
	return count;
}

static ssize_t effect_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	const char *name;

	switch (data->effect) {
	case 0x02: name = "breathing"; break;
	case 0x03: name = "wave"; break;
	case 0x04: name = "random"; break;
	case 0x05: name = "rainbow"; break;
	case 0x06: name = "ripple"; break;
	case 0x09: name = "marquee"; break;
	case 0x0A: name = "raindrop"; break;
	case 0x0E: name = "aurora"; break;
	case 0x11: name = "fireworks"; break;
	case 0x0B: name = "reactive"; break;
	case 51:   name = "monocolor"; break;
	case 0xFF: name = "per-key"; break;
	default:   name = "off"; break;
	}
	return sysfs_emit(buf, "%s\n", name);
}
static DEVICE_ATTR_RW(effect);

static ssize_t speed_store(struct device *dev, struct device_attribute *attr,
			   const char *buf, size_t count)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	unsigned int val;

	if (kstrtouint(buf, 10, &val) || val > 9)
		return -EINVAL;

	mutex_lock(&data->lock);
	data->speed = val;
	mutex_unlock(&data->lock);
	return count;
}

static ssize_t speed_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	return sysfs_emit(buf, "%u\n", data->speed);
}
static DEVICE_ATTR_RW(speed);

static ssize_t color_index_store(struct device *dev, struct device_attribute *attr,
				 const char *buf, size_t count)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	unsigned int val;

	if (kstrtouint(buf, 10, &val) || val > 8)
		return -EINVAL;

	mutex_lock(&data->lock);
	data->color_index = val;
	mutex_unlock(&data->lock);
	return count;
}

static ssize_t color_index_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	return sysfs_emit(buf, "%u\n", data->color_index);
}
static DEVICE_ATTR_RW(color_index);

static ssize_t reactive_store(struct device *dev, struct device_attribute *attr,
			      const char *buf, size_t count)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	unsigned int val;

	if (kstrtouint(buf, 10, &val) || val > 1)
		return -EINVAL;

	mutex_lock(&data->lock);
	data->reactive = val;
	mutex_unlock(&data->lock);
	return count;
}

static ssize_t reactive_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	return sysfs_emit(buf, "%u\n", data->reactive);
}
static DEVICE_ATTR_RW(reactive);

static ssize_t direction_store(struct device *dev, struct device_attribute *attr,
			       const char *buf, size_t count)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	unsigned int val;

	if (kstrtouint(buf, 10, &val) || val > 4)
		return -EINVAL;

	mutex_lock(&data->lock);
	data->direction = val;
	mutex_unlock(&data->lock);
	return count;
}

static ssize_t direction_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	return sysfs_emit(buf, "%u\n", data->direction);
}
static DEVICE_ATTR_RW(direction);

static ssize_t audio_mode_store(struct device *dev, struct device_attribute *attr,
				const char *buf, size_t count)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	unsigned int val;

	if (kstrtouint(buf, 10, &val) || val > 4)
		return -EINVAL;

	mutex_lock(&data->lock);
	data->audio_mode = val;
	/* Send audio command immediately */
	{
		u8 audio_cmd[8] = { 0x02, val, data->audio_sensitivity, 0, 0, 0, 0, 0 };
		ite8291r3_send_ctrl(data, audio_cmd, 8);
	}
	mutex_unlock(&data->lock);
	return count;
}

static ssize_t audio_mode_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	return sysfs_emit(buf, "%u\n", data->audio_mode);
}
static DEVICE_ATTR_RW(audio_mode);

static ssize_t audio_sensitivity_store(struct device *dev, struct device_attribute *attr,
				       const char *buf, size_t count)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	unsigned int val;

	if (kstrtouint(buf, 10, &val) || val > 255)
		return -EINVAL;

	mutex_lock(&data->lock);
	data->audio_sensitivity = val;
	/* Re-send audio command if audio mode is active */
	if (data->audio_mode > 0) {
		u8 audio_cmd[8] = { 0x02, data->audio_mode, val, 0, 0, 0, 0, 0 };
		ite8291r3_send_ctrl(data, audio_cmd, 8);
	}
	mutex_unlock(&data->lock);
	return count;
}

static ssize_t audio_sensitivity_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	return sysfs_emit(buf, "%u\n", data->audio_sensitivity);
}
static DEVICE_ATTR_RW(audio_sensitivity);

/* Palette sysfs: write "index r g b" to set a palette slot (index 1-7) */
static ssize_t palette_store(struct device *dev, struct device_attribute *attr,
			     const char *buf, size_t count)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	unsigned int idx, r, g, b;

	if (sscanf(buf, "%u %u %u %u", &idx, &r, &g, &b) != 4)
		return -EINVAL;
	if (idx < 1 || idx > 7 || r > 255 || g > 255 || b > 255)
		return -EINVAL;

	mutex_lock(&data->lock);
	ite8291r3_set_palette(data, idx, r, g, b);
	mutex_unlock(&data->lock);
	return count;
}
static DEVICE_ATTR_WO(palette);

static ssize_t key_colors_store(struct device *dev, struct device_attribute *attr,
				const char *buf, size_t count)
{
	struct led_classdev *cdev = dev_get_drvdata(dev);
	struct ite8291r3_data *data = container_of(cdev, struct ite8291r3_data, led_cdev);
	const char *p = buf;
	int row, col, r, g, b;
	int ret = 0, i;

	mutex_lock(&data->lock);

	for (i = 0; i < NUM_ROWS; i++)
		memset(data->row_data[i], 0, ROW_BUFFER_LEN);

	while (sscanf(p, "%d %d %d %d %d", &row, &col, &r, &g, &b) == 5) {
		if (row >= 0 && row < NUM_ROWS && col >= 0 && col < NUM_COLS) {
			data->row_data[row][ROW_RED_OFFSET + col] = (u8)r;
			data->row_data[row][ROW_GREEN_OFFSET + col] = (u8)g;
			data->row_data[row][ROW_BLUE_OFFSET + col] = (u8)b;
		}
		for (i = 0; i < 5 && *p; i++) {
			while (*p && *p != ' ' && *p != '\n') p++;
			while (*p == ' ') p++;
		}
		if (*p == '\n') p++;
	}

	/*
	 * Enter user/direct mode BEFORE streaming rows so the chip's animation
	 * engine is disabled.  save=0 — no flash write (avoids wear/brick risk;
	 * userspace daemon re-pushes on resume anyway).
	 *
	 * 15ms after the mode-switch command gives the MCU time to finish
	 * switching its internal state machine before we start sending row data.
	 */
	ite8291r3_enable_user_mode(data, data->brightness, 0);
	usleep_range(14000, 16000);
	data->effect = 0xFF; /* per-key mode */
	for (i = 0; i < NUM_ROWS; i++) {
		ret = ite8291r3_set_row_index(data, i);
		if (ret) break;
		ret = ite8291r3_send_row(data, i);
		if (ret) break;
	}

	/*
	 * Latch: a second enable_user_mode after the row stream copies the
	 * staging buffer to the active PWM matrix registers (double-buffer
	 * flip).  Without this the chip may show a partial or stale frame.
	 *
	 * 15ms inter-packet delay required between last row packet and the latch
	 * command — ITE8291R3 MCU needs time to finish DMA-copying the final rows
	 * into staging RAM.  Without this delay, rows 1-3 (middle of the matrix)
	 * may not be fully staged, causing those keys (R, F, V, N etc.) to show
	 * the previous frame's dimmer/stale colours intermittently.
	 */
	usleep_range(14000, 16000);
	if (!ret)
		ite8291r3_enable_user_mode(data, data->brightness, 0);

	mutex_unlock(&data->lock);
	return ret ? ret : count;
}
static DEVICE_ATTR_WO(key_colors);

static struct attribute *ite8291r3_attrs[] = {
	&dev_attr_color.attr,
	&dev_attr_effect.attr,
	&dev_attr_speed.attr,
	&dev_attr_color_index.attr,
	&dev_attr_reactive.attr,
	&dev_attr_direction.attr,
	&dev_attr_audio_mode.attr,
	&dev_attr_audio_sensitivity.attr,
	&dev_attr_palette.attr,
	&dev_attr_key_colors.attr,
	NULL,
};

static const struct attribute_group ite8291r3_group = {
	.attrs = ite8291r3_attrs,
};

/* --- USB driver --- */

static int ite8291r3_probe(struct usb_interface *intf, const struct usb_device_id *id)
{
	struct usb_device *udev = interface_to_usbdev(intf);
	struct usb_host_interface *iface_desc = intf->cur_altsetting;
	struct ite8291r3_data *data;
	struct usb_endpoint_descriptor *ep;
	int i, ret;

	/* Only bind to interface 1 */
	if (iface_desc->desc.bInterfaceNumber != 1)
		return -ENODEV;

	/* Check bcdDevice == 0x0003 (revision 3) */
	if (le16_to_cpu(udev->descriptor.bcdDevice) != 0x0003)
		return -ENODEV;

	data = kzalloc(sizeof(*data), GFP_KERNEL);
	if (!data)
		return -ENOMEM;

	data->udev = usb_get_dev(udev);
	data->intf = intf;
	data->brightness = 25;
	data->r = 255; data->g = 255; data->b = 255;
	data->speed = 5;
	data->color_index = 8;
	data->reactive = 0;
	data->direction = 1;  /* default: right */
	data->audio_mode = 0;
	data->audio_sensitivity = 0x80;	/* standard sensitivity */
	data->ep_out = -1;
	mutex_init(&data->lock);

	for (i = 0; i < iface_desc->desc.bNumEndpoints; i++) {
		ep = &iface_desc->endpoint[i].desc;
		if (usb_endpoint_dir_out(ep)) {
			data->ep_out = ep->bEndpointAddress;
			break;
		}
	}

	if (data->ep_out < 0) {
		dev_err(&intf->dev, "No OUT endpoint found\n");
		usb_put_dev(udev);
		kfree(data);
		return -ENODEV;
	}

	usb_set_intfdata(intf, data);

	data->led_cdev.name = "ite8291r3::kbd_backlight";
	data->led_cdev.max_brightness = 255;
	data->led_cdev.brightness_set = ite8291r3_led_set;
	data->led_cdev.brightness_get = ite8291r3_led_get;

	ret = led_classdev_register(&intf->dev, &data->led_cdev);
	if (ret) {
		usb_put_dev(udev);
		kfree(data);
		return ret;
	}

	/* Add custom sysfs attrs to the LED device */
	ret = sysfs_create_group(&data->led_cdev.dev->kobj, &ite8291r3_group);
	if (ret)
		dev_warn(&intf->dev, "Failed to create sysfs group: %d\n", ret);

	/*
	 * Palette reprogramming: Exhaustively tested on FW 16.04.00.00 (PID 6006):
	 *   - CMD 0x07 via wValue 0x0300 — silently ignored
	 *   - CMD 0x07 via wValue 0x03CC — silently ignored
	 *   - CMD 0x14 via wValue 0x0300 — silently ignored
	 *   - CMD 0x14 via wValue 0x03CC — silently ignored
	 * The palette LUT is ROM-burned on this Tongfang variant.
	 * Palette code and sysfs kept for potential future firmware/hardware.
	 */

	dev_info(&intf->dev, "ITE8291R3 keyboard backlight registered (ep_out=0x%02x)\n", data->ep_out);
	return 0;
}

static void ite8291r3_disconnect(struct usb_interface *intf)
{
	struct ite8291r3_data *data = usb_get_intfdata(intf);

	if (!data)
		return;

	sysfs_remove_group(&data->led_cdev.dev->kobj, &ite8291r3_group);
	led_classdev_unregister(&data->led_cdev);
	usb_put_dev(data->udev);
	kfree(data);
}

/*
 * reset_resume — called after USB re-enumeration on wake from suspend.
 *
 * The chip loses all volatile state on resume (USB power is cut during S3/S0ix).
 * Re-push the full cached state so the keyboard comes back exactly as the user
 * left it, without any userspace intervention.
 *
 * Per-key mode (0xFF): re-enter user mode, push all 6 rows, latch.
 * Animated effects:   re-send the effect command with saved parameters.
 * brightness == 0:    turn off cleanly.
 */
static int ite8291r3_reset_resume(struct usb_interface *intf)
{
	struct ite8291r3_data *data = usb_get_intfdata(intf);
	int i, ret = 0;

	if (!data)
		return 0;

	mutex_lock(&data->lock);

	if (data->brightness == 0) {
		ite8291r3_turn_off(data);
		goto out;
	}

	if (data->effect == 0xFF) {
		/* Per-key: re-enter direct mode and push all cached rows */
		ite8291r3_enable_user_mode(data, data->brightness, 0);
		for (i = 0; i < NUM_ROWS; i++) {
			ret = ite8291r3_set_row_index(data, i);
			if (ret) break;
			ret = ite8291r3_send_row(data, i);
			if (ret) break;
		}
		if (!ret)
			ite8291r3_enable_user_mode(data, data->brightness, 0); /* latch */
	} else if (data->effect == 51) {
		/* Monocolor */
		ite8291r3_set_mono_color(data, data->r, data->g, data->b, data->brightness, 0);
	} else if (data->effect == 0) {
		ite8291r3_turn_off(data);
	} else {
		/* Animated effect */
		u8 byte6 = (data->effect == 0x03) ? data->direction : data->reactive;
		ite8291r3_set_effect_raw(data, 0x02, data->effect, data->speed,
					 data->brightness, data->color_index, byte6, 0);
	}

out:
	mutex_unlock(&data->lock);
	return ret;
}

static const struct usb_device_id ite8291r3_id_table[] = {
	{ USB_DEVICE(ITE8291R3_VENDOR_ID, 0x6004) },
	{ USB_DEVICE(ITE8291R3_VENDOR_ID, 0x6006) },
	{ USB_DEVICE(ITE8291R3_VENDOR_ID, 0xCE00) },
	{ }
};
MODULE_DEVICE_TABLE(usb, ite8291r3_id_table);

static struct usb_driver ite8291r3_usb_driver = {
	.name = "ite8291r3",
	.id_table = ite8291r3_id_table,
	.probe = ite8291r3_probe,
	.disconnect = ite8291r3_disconnect,
	.reset_resume = ite8291r3_reset_resume,
};
module_usb_driver(ite8291r3_usb_driver);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("NUC Linux Studio");
MODULE_DESCRIPTION("ITE8291R3 USB keyboard backlight driver");
