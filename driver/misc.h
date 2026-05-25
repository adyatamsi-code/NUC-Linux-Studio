// SPDX-License-Identifier: GPL-2.0
#ifndef NUC_WMI_MISC_H
#define NUC_WMI_MISC_H

#include <linux/types.h>

/* ========================================================================== */

int nuc_wmi_rfkill_get_wifi_state(void);

int nuc_wmi_fn_lock_get_state(void);
int nuc_wmi_fn_lock_set_state(bool state);

#endif /* NUC_WMI_MISC_H */
