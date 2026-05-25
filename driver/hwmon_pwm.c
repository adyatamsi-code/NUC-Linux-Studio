// SPDX-License-Identifier: GPL-2.0
#include "pr.h"

#include <linux/device.h>
#include <linux/hwmon.h>
#include <linux/hwmon-sysfs.h>
#include <linux/init.h>
#include <linux/lockdep.h>
#include <linux/mutex.h>
#include <linux/sysfs.h>
#include <linux/types.h>

#include "fan.h"
#include "features.h"
#include "hwmon_pwm.h"
#include "pdev.h"

/* ========================================================================== */

static struct device *nuc_wmi_hwmon_pwm_dev;

/* ========================================================================== */

static umode_t nuc_wmi_hwmon_pwm_is_visible(const void *data, enum hwmon_sensor_types type,
					 u32 attr, int channel)
{
	if (type != hwmon_pwm)
		return 0;

	switch (attr) {
	case hwmon_pwm_input:
	case hwmon_pwm_enable:
		return 0644;
	default:
		return 0;
	}
}

static int nuc_wmi_hwmon_pwm_read(struct device *device, enum hwmon_sensor_types type,
			       u32 attr, int channel, long *value)
{
	int err;

	switch (type) {
	case hwmon_pwm:
		switch (attr) {
		case hwmon_pwm_enable:
			err = nuc_wmi_fan_get_mode();
			if (err < 0)
				return err;

			*value = err;
			break;
		case hwmon_pwm_input:
			err = nuc_wmi_fan_get_pwm(channel);
			if (err < 0)
				return err;

			*value = err;
			break;
		default:
			return -EOPNOTSUPP;
		}
		break;
	default:
		return -EOPNOTSUPP;
	}

	return 0;
}

static int nuc_wmi_hwmon_pwm_write(struct device *device, enum hwmon_sensor_types type,
			    u32 attr, int channel, long value)
{
	switch (type) {
	case hwmon_pwm:
		switch (attr) {
		case hwmon_pwm_enable:
			return nuc_wmi_fan_set_mode(value);
		case hwmon_pwm_input:
			return nuc_wmi_fan_set_pwm(channel, value);
		default:
			return -EOPNOTSUPP;
		}
	default:
		return -EOPNOTSUPP;
	}

	return 0;
}

static const struct hwmon_channel_info *nuc_wmi_hwmon_pwm_ch_info[] = {
	HWMON_CHANNEL_INFO(pwm, HWMON_PWM_INPUT | HWMON_PWM_ENABLE,
			        HWMON_PWM_INPUT),
	NULL
};

static const struct hwmon_ops nuc_wmi_hwmon_pwm_ops = {
	.is_visible  = nuc_wmi_hwmon_pwm_is_visible,
	.read        = nuc_wmi_hwmon_pwm_read,
	.write       = nuc_wmi_hwmon_pwm_write,
};

static const struct hwmon_chip_info nuc_wmi_hwmon_pwm_chip_info = {
	.ops  = &nuc_wmi_hwmon_pwm_ops,
	.info =  nuc_wmi_hwmon_pwm_ch_info,
};

/* ========================================================================== */

int __init nuc_wmi_hwmon_pwm_setup(void)
{
	/* NUC X15: fan_boost feature bit may not be set in SUPPORT_1 register,
	 * but the hardware does support PWM fan control. Always register. */

	nuc_wmi_hwmon_pwm_dev = hwmon_device_register_with_info(
		&nuc_wmi_platform_dev->dev, KBUILD_MODNAME ".hwmon.pwm", NULL,
		&nuc_wmi_hwmon_pwm_chip_info, NULL);

	if (IS_ERR(nuc_wmi_hwmon_pwm_dev))
		return PTR_ERR(nuc_wmi_hwmon_pwm_dev);

	return 0;
}

void nuc_wmi_hwmon_pwm_cleanup(void)
{
	if (!IS_ERR_OR_NULL(nuc_wmi_hwmon_pwm_dev))
		hwmon_device_unregister(nuc_wmi_hwmon_pwm_dev);
}
