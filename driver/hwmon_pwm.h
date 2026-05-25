// SPDX-License-Identifier: GPL-2.0
#ifndef NUC_WMI_HWMON_PWM_H
#define NUC_WMI_HWMON_PWM_H

#include <linux/init.h>

int  __init nuc_wmi_hwmon_pwm_setup(void);
void        nuc_wmi_hwmon_pwm_cleanup(void);

#endif /* NUC_WMI_HWMON_PWM_H */
