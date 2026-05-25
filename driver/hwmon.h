// SPDX-License-Identifier: GPL-2.0
#ifndef NUC_WMI_HWMON_H
#define NUC_WMI_HWMON_H

#if IS_ENABLED(CONFIG_HWMON)

#include <linux/init.h>

int  __init nuc_wmi_hwmon_setup(void);
void        nuc_wmi_hwmon_cleanup(void);

#else

static inline int nuc_wmi_hwmon_setup(void)
{
	return 0;
}

static inline void nuc_wmi_hwmon_cleanup(void)
{

}

#endif

#endif /* NUC_WMI_HWMON_H */
