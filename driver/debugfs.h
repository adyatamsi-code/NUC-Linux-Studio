// SPDX-License-Identifier: GPL-2.0
#ifndef NUC_WMI_DEBUGFS_H
#define NUC_WMI_DEBUGFS_H

#if IS_ENABLED(CONFIG_DEBUG_FS)

#include <linux/init.h>

int  __init nuc_wmi_debugfs_setup(void);
void        nuc_wmi_debugfs_cleanup(void);

#else

static inline int nuc_wmi_debugfs_setup(void)
{
	return 0;
}

static inline void nuc_wmi_debugfs_cleanup(void)
{

}

#endif

#endif /* NUC_WMI_DEBUGFS_H */
