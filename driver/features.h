// SPDX-License-Identifier: GPL-2.0
#ifndef NUC_WMI_FEATURES_H
#define NUC_WMI_FEATURES_H

#include <linux/init.h>
#include <linux/types.h>

struct nuc_wmi_features_struct {
	bool super_key_lock    : 1;
	bool lightbar          : 1;
	bool fan_boost         : 1;
	bool fn_lock           : 1;
	bool batt_charge_limit : 1;
	bool fan_extras        : 1; /* duty cycle reduction, always on mode */
};

/* ========================================================================== */

extern struct nuc_wmi_features_struct nuc_wmi_features;

/* ========================================================================== */

int __init nuc_wmi_check_features(void);

#endif /* NUC_WMI_FEATURES_H */
