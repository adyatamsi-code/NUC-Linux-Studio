// SPDX-License-Identifier: GPL-2.0
#ifndef NUC_WMI_HWMON_FAN_H
#define NUC_WMI_HWMON_FAN_H

#include <linux/init.h>

int  __init nuc_wmi_hwmon_fan_setup(void);
void        nuc_wmi_hwmon_fan_cleanup(void);

#endif /* NUC_WMI_HWMON_FAN_H */
