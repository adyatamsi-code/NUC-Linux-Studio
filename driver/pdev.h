// SPDX-License-Identifier: GPL-2.0
#ifndef NUC_WMI_PDEV_H
#define NUC_WMI_PDEV_H

#include <linux/init.h>
#include <linux/platform_device.h>

/* ========================================================================== */

extern struct platform_device *nuc_wmi_platform_dev;
extern struct device *nuc_wmi_pprof_dev;

/* ========================================================================== */

int  __init nuc_wmi_pdev_setup(void);
void        nuc_wmi_pdev_cleanup(void);

/* Performance profile tracking (software-based) */
int  nuc_wmi_get_perf_profile(void);
void nuc_wmi_cycle_perf_profile(void);

#endif /* NUC_WMI_PDEV_H */
