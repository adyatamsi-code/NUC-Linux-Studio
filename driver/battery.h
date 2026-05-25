// SPDX-License-Identifier: GPL-2.0
#ifndef NUC_WMI_BATTERY_H
#define NUC_WMI_BATTERY_H

#if IS_ENABLED(CONFIG_ACPI_BATTERY)

#include <linux/init.h>

int  __init nuc_wmi_battery_setup(void);
void        nuc_wmi_battery_cleanup(void);

#else

static inline int nuc_wmi_battery_setup(void)
{
	return 0;
}

static inline void nuc_wmi_battery_cleanup(void)
{

}

#endif

#endif /* NUC_WMI_BATTERY_H */
