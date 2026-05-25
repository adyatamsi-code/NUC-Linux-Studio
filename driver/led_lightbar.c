// SPDX-License-Identifier: GPL-2.0
#include "pr.h"

#include <linux/init.h>
#include <linux/leds.h>
#include <linux/moduleparam.h>
#include <linux/types.h>
#include <linux/delay.h>

#include "util.h"
#include "ec.h"
#include "features.h"
#include "led_lightbar.h"
#include "pdev.h"

/* ========================================================================== */

#if IS_ENABLED(CONFIG_LEDS_CLASS)

enum nuc_wmi_lightbar_color {
	LIGHTBAR_RED,
	LIGHTBAR_GREEN,
	LIGHTBAR_BLUE,
	LIGHTBAR_COLOR_COUNT
};

/* EC color addresses — RGB order per original qc71_laptop driver */
static const uint16_t lightbar_color_addrs[LIGHTBAR_COLOR_COUNT] = {
	[LIGHTBAR_RED]   = 0x0749,
	[LIGHTBAR_GREEN] = 0x074A,
	[LIGHTBAR_BLUE]  = 0x074B,
};

static const uint8_t lightbar_colors[LIGHTBAR_COLOR_COUNT] = {
	LIGHTBAR_RED,
	LIGHTBAR_GREEN,
	LIGHTBAR_BLUE,
};

/* ========================================================================== */

static bool nolightbar;
module_param(nolightbar, bool, 0444);
MODULE_PARM_DESC(nolightbar, "do not register the lightbar to the leds subsystem (default=false)");

static bool lightbar_led_registered;
static u8 current_multi_intensity[3] = {255, 255, 255};

/* ========================================================================== */

static inline int nuc_wmi_lightbar_get_status(void)
{
	return ec_read_byte(LIGHTBAR_CTRL_ADDR); // 0x0748
}

static inline int nuc_wmi_lightbar_write_ctrl(uint8_t ctrl)
{
	return ec_write_byte(LIGHTBAR_CTRL_ADDR, ctrl);
}

/* ========================================================================== */

static int nuc_wmi_lightbar_switch(uint8_t mask, bool on)
{
	int status;
	int err;

	if (mask != LIGHTBAR_CTRL_S0_OFF && mask != LIGHTBAR_CTRL_S3_OFF)
		return -EINVAL;

	status = nuc_wmi_lightbar_get_status();

	if (status < 0)
		return status;

	err = nuc_wmi_lightbar_write_ctrl(SET_BIT(status, mask, !on));
	if (err)
		return err;

	/* Flush EC shadow registers */
	return ec_write_byte(TRIGGER_1_ADDR, TRIGGER_1_LIGHTBAR);
}

static int nuc_wmi_lightbar_set_color_level(uint16_t addr, uint8_t level)
{
	if (level > LIGHTBAR_COLOR_MAX)
		level = LIGHTBAR_COLOR_MAX;
	return ec_write_byte(addr, level);
}

static int nuc_wmi_lightbar_set_rainbow_mode(bool on)
{
	int status = nuc_wmi_lightbar_get_status();
	int err;

	if (status < 0)
		return status;

	if (on) {
		/* Clear all mode bits + S0_OFF, then set rainbow */
		status = (status & ~(LIGHTBAR_CTRL_MODE_MASK | LIGHTBAR_CTRL_S0_OFF))
			 | LIGHTBAR_CTRL_RAINBOW;
	} else {
		/* Clear rainbow, set static */
		status = (status & ~LIGHTBAR_CTRL_MODE_MASK) | LIGHTBAR_CTRL_STATIC;
	}
	err = nuc_wmi_lightbar_write_ctrl(status);
	if (err)
		return err;

	/* Flush EC shadow registers to LED controller */
	return ec_write_byte(TRIGGER_1_ADDR, TRIGGER_1_LIGHTBAR);
}

static int nuc_wmi_lightbar_set_breathing_mode(bool on)
{
	int status = nuc_wmi_lightbar_get_status();
	int err;

	if (status < 0)
		return status;

	if (on) {
		/* Clear all mode bits + S0_OFF, then set breathing */
		status = (status & ~(LIGHTBAR_CTRL_MODE_MASK | LIGHTBAR_CTRL_S0_OFF))
			 | LIGHTBAR_CTRL_BREATH;
	} else {
		/* Clear breathing, set static */
		status = (status & ~LIGHTBAR_CTRL_MODE_MASK) | LIGHTBAR_CTRL_STATIC;
	}
	err = nuc_wmi_lightbar_write_ctrl(status);
	if (err)
		return err;

	/* Flush EC shadow registers to LED controller */
	return ec_write_byte(TRIGGER_1_ADDR, TRIGGER_1_LIGHTBAR);
}

/* ========================================================================== */
/* lightbar attrs */

static ssize_t lightbar_s3_show(struct device *dev,
				struct device_attribute *attr, char *buf)
{
	int value = nuc_wmi_lightbar_get_status();

	if (value < 0)
		return value;

	return sprintf(buf, "%d\n", !(value & LIGHTBAR_CTRL_S3_OFF));
}

static ssize_t lightbar_s3_store(struct device *dev, struct device_attribute *attr,
				 const char *buf, size_t count)
{
	int err;
	bool value;

	if (kstrtobool(buf, &value))
		return -EINVAL;

	err = nuc_wmi_lightbar_switch(LIGHTBAR_CTRL_S3_OFF, value);

	if (err)
		return err;

	return count;
}

static ssize_t rainbow_animation_show(struct device *dev,
				     struct device_attribute *attr, char *buf)
{
	int status = nuc_wmi_lightbar_get_status();

	if (status < 0)
		return status;

	return sprintf(buf, "%d\n", !!(status & LIGHTBAR_CTRL_RAINBOW));
}

static ssize_t rainbow_animation_store(struct device *dev, struct device_attribute *attr,
				      const char *buf, size_t count)
{
	int err;
	bool value;

	if (kstrtobool(buf, &value))
		return -EINVAL;

	err = nuc_wmi_lightbar_set_rainbow_mode(value);

	if (err)
		return err;

	return count;
}

static ssize_t breathing_animation_show(struct device *dev,
				     struct device_attribute *attr, char *buf)
{
	int status = nuc_wmi_lightbar_get_status();

	if (status < 0)
		return status;

	return sprintf(buf, "%d\n", !!(status & LIGHTBAR_CTRL_BREATH));
}

static ssize_t breathing_animation_store(struct device *dev, struct device_attribute *attr,
				      const char *buf, size_t count)
{
	int err;
	bool value;

	if (kstrtobool(buf, &value))
		return -EINVAL;

	err = nuc_wmi_lightbar_set_breathing_mode(value);

	if (err)
		return err;

	return count;
}

static ssize_t multi_intensity_show(struct device *dev,
				    struct device_attribute *attr, char *buf)
{
	return sprintf(buf, "%u %u %u\n", current_multi_intensity[0], current_multi_intensity[1], current_multi_intensity[2]);
}

static ssize_t multi_intensity_store(struct device *dev, struct device_attribute *attr,
				     const char *buf, size_t count)
{
	unsigned int r, g, b;
	uint8_t hw_b, hw_g, hw_r;

	if (sscanf(buf, "%u %u %u", &r, &g, &b) != 3)
		return -EINVAL;

	current_multi_intensity[0] = min(r, 255U);
	current_multi_intensity[1] = min(g, 255U);
	current_multi_intensity[2] = min(b, 255U);

	/*
	 * Scale 0-255 to 0-36 for the EC (OEM firmware range).
	 * Writing values > 36 risks overflow on some BIOS revisions.
	 *
	 * Register order is RGB: 0x0749=R, 0x074A=G, 0x074B=B
	 * per the original qc71_laptop driver.
	 * DO NOT write past 0x074B — 0x074E controls LID/AC flags
	 * and 0x0751 is the fan duty cycle register!
	 */
	hw_r = (current_multi_intensity[0] * LIGHTBAR_COLOR_MAX + 127) / 255;
	hw_g = (current_multi_intensity[1] * LIGHTBAR_COLOR_MAX + 127) / 255;
	hw_b = (current_multi_intensity[2] * LIGHTBAR_COLOR_MAX + 127) / 255;

	/* Set global lightbar brightness to max */
	ec_write_byte(LIGHTBAR_BRIGHTNESS_ADDR, 0x64);

	/* Set static mode, clearing animation bits but preserving S3 power state.
	 * Also clear S0_OFF so the lightbar is visible. */
	{
		int ctrl = nuc_wmi_lightbar_get_status();
		if (ctrl >= 0)
			ec_write_byte(LIGHTBAR_CTRL_ADDR,
				      (ctrl & ~(LIGHTBAR_CTRL_MODE_MASK | LIGHTBAR_CTRL_S0_OFF))
				      | LIGHTBAR_CTRL_STATIC);
	}

	/* Write colors in RGB order to 0x0749-0x074B only */
	nuc_wmi_lightbar_set_color_level(LIGHTBAR_RED_ADDR,   hw_r);
	nuc_wmi_lightbar_set_color_level(LIGHTBAR_GREEN_ADDR, hw_g);
	nuc_wmi_lightbar_set_color_level(LIGHTBAR_BLUE_ADDR,  hw_b);

	/* Trigger lightbar update */
	ec_write_byte(TRIGGER_1_ADDR, TRIGGER_1_LIGHTBAR);

	return count;
}

static int nuc_wmi_lightbar_led_set_brightness(struct led_classdev *led_cdev,
					    enum led_brightness brightness)
{
	if (brightness) {
		ec_write_byte(LIGHTBAR_BRIGHTNESS_ADDR, 0x64);
		return nuc_wmi_lightbar_switch(LIGHTBAR_CTRL_S0_OFF, 1);
	} else {
		ec_write_byte(LIGHTBAR_BRIGHTNESS_ADDR, 0x00);
		return nuc_wmi_lightbar_switch(LIGHTBAR_CTRL_S0_OFF, 0);
	}
}

/* ========================================================================== */

static DEVICE_ATTR(brightness_s3, 0664, lightbar_s3_show,      lightbar_s3_store);
static DEVICE_ATTR(rainbow_animation,  0664, rainbow_animation_show, rainbow_animation_store);
static DEVICE_ATTR(breathing_animation,  0664, breathing_animation_show, breathing_animation_store);
static DEVICE_ATTR(multi_intensity,  0664, multi_intensity_show, multi_intensity_store);

static struct attribute *nuc_wmi_lightbar_led_attrs[] = {
	&dev_attr_brightness_s3.attr,
	&dev_attr_rainbow_animation.attr,
	&dev_attr_breathing_animation.attr,
	&dev_attr_multi_intensity.attr,
	NULL
};

ATTRIBUTE_GROUPS(nuc_wmi_lightbar_led);

static struct led_classdev nuc_wmi_lightbar_led = {
	.name                    = "uniwill:multicolor:status",
	.max_brightness          = 255,
	.brightness              = 255,
	.brightness_set_blocking = nuc_wmi_lightbar_led_set_brightness,
	.groups                  = nuc_wmi_lightbar_led_groups,
};

/* ========================================================================== */

int __init nuc_wmi_led_lightbar_setup(void)
{
	int err;

	if (nolightbar)
		return -ENODEV;

	err = led_classdev_register(&nuc_wmi_platform_dev->dev, &nuc_wmi_lightbar_led);

	if (!err)
		lightbar_led_registered = true;

	return err;
}

void nuc_wmi_led_lightbar_cleanup(void)
{
	if (lightbar_led_registered) {
		led_classdev_unregister(&nuc_wmi_lightbar_led);
	}
}

#endif