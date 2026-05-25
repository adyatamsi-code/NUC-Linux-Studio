// SPDX-License-Identifier: GPL-2.0
/* ========================================================================== */
/* https://www.intel.com/content/dam/support/us/en/documents/laptops/whitebook/NUC_WMI_PROD_SPEC.pdf
 *
 *
 * based on the following resources:
 *  - https://lwn.net/Articles/391230/
 *  - http://blog.nietrzeba.pl/2011/12/mof-decompilation.html
 *  - https://github.com/tuxedocomputers/tuxedo-cc-wmi/
 *  - https://github.com/tuxedocomputers/tuxedo-keyboard/
 *  - Control Center for Microsoft Windows
 *  - http://forum.notebookreview.com/threads/tongfang-gk7cn6s-gk7cp0s-gk7cp7s.825461/page-54
 */
/* ========================================================================== */
#include "pr.h"

#include <linux/dmi.h>
#include <linux/init.h>
#include <linux/kconfig.h>
#include <linux/module.h>
#include <linux/string.h>
#include <linux/types.h>
#include <linux/wmi.h>

#include "ec.h"
#include "features.h"
#include "wmi.h"

/* submodules */
#include "pdev.h"
#include "events.h"
#include "hwmon.h"
#include "battery.h"
#include "led_lightbar.h"
#include "debugfs.h"

/* ========================================================================== */

#define SUBMODULE_ENTRY(_name, _req) { .name = #_name, .init = nuc_wmi_ ## _name ## _setup, .cleanup = nuc_wmi_ ## _name ## _cleanup, .required = _req }

static struct nuc_wmi_submodule {
	const char *name;

	bool required    : 1,
	     initialized : 1;

	int (*init)(void);
	void (*cleanup)(void);
} nuc_wmi_submodules[] __refdata = {
	SUBMODULE_ENTRY(pdev, true), /* must be first */
	SUBMODULE_ENTRY(wmi_events, false),
	SUBMODULE_ENTRY(hwmon, false),
	SUBMODULE_ENTRY(battery, false),
	SUBMODULE_ENTRY(led_lightbar, false),
	SUBMODULE_ENTRY(debugfs, false),
};

#undef SUBMODULE_ENTRY

static void do_cleanup(void)
{
	int i;

	for (i = ARRAY_SIZE(nuc_wmi_submodules) - 1; i >= 0; i--) {
		const struct nuc_wmi_submodule *sm = &nuc_wmi_submodules[i];

		if (sm->initialized)
			sm->cleanup();
	}
}

static int __init nuc_wmi_laptop_module_init(void)
{
	int err = 0, i;

	if (!wmi_has_guid(NUC_WMI_WMBC_GUID)) {
		pr_err("WMI GUID not found\n");
		err = -ENODEV; goto out;
	}

	err = ec_read_byte(PROJ_ID_ADDR);
	if (err < 0) {
		pr_err("failed to query project id: %d\n", err);
		goto out;
	}

	pr_info("project id: %d\n", err);

	err = ec_read_byte(PLATFORM_ID_ADDR);
	if (err < 0) {
		pr_err("failed to query platform id: %d\n", err);
		goto out;
	}

	pr_info("platform id: %d\n", err);

	err = nuc_wmi_check_features();
	if (err) {
		pr_err("cannot check system features: %d\n", err);
		goto out;
	}

	pr_info("supported features:");
	if (nuc_wmi_features.super_key_lock)    pr_cont(" super-key-lock");
	if (nuc_wmi_features.lightbar)          pr_cont(" lightbar");
	if (nuc_wmi_features.fan_boost)         pr_cont(" fan-boost");
	if (nuc_wmi_features.fn_lock)           pr_cont(" fn-lock");
	if (nuc_wmi_features.batt_charge_limit) pr_cont(" charge-limit");
	if (nuc_wmi_features.fan_extras)        pr_cont(" fan-extras");
	pr_cont("\n");

	/*
	 * Clear manual mode (CTRL_1 bit 0) so the EC handles the
	 * performance profile button autonomously. If the user wants
	 * manual fan control, they can re-enable it via sysfs.
	 */
	{
		int ctrl1 = ec_read_byte(CTRL_1_ADDR);
		if (ctrl1 >= 0 && (ctrl1 & CTRL_1_MANUAL_MODE)) {
			ec_write_byte(CTRL_1_ADDR, ctrl1 & ~CTRL_1_MANUAL_MODE);
			pr_info("cleared manual mode for EC button support\n");
		}
	}

	/*
	 * Restore automatic fan control in FAN_CTRL register (0x0751).
	 * If the app previously set FAN_BOOST, fans will be stuck at
	 * whatever PWM was last written. Clear boost and set AUTO.
	 */
	{
		int fanctrl = ec_read_byte(FAN_CTRL_ADDR);
		if (fanctrl >= 0 && (fanctrl & FAN_CTRL_FAN_BOOST)) {
			ec_write_byte(FAN_CTRL_ADDR,
				      (fanctrl & 0xb0) | 0x80 | 0x04);
			pr_info("restored automatic fan control\n");
		}
	}

	for (i = 0; i < ARRAY_SIZE(nuc_wmi_submodules); i++) {
		struct nuc_wmi_submodule *sm = &nuc_wmi_submodules[i];

		err = sm->init();
		if (err) {
			pr_warn("failed to initialize %s submodule: %d\n", sm->name, err);
			if (sm->required)
				goto out;
		} else {
			sm->initialized = true;
		}
	}

	err = 0;

out:
	if (err)
		do_cleanup();
	else
		pr_info("module loaded\n");

	return err;
}

static void __exit nuc_wmi_laptop_module_cleanup(void)
{
	do_cleanup();
	pr_info("module unloaded\n");
}

/* ========================================================================== */

module_init(nuc_wmi_laptop_module_init);
module_exit(nuc_wmi_laptop_module_cleanup);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Barnabás Pőcze <pobrn@protonmail.com>");
MODULE_DESCRIPTION("NUC WMI laptop platform driver");
MODULE_ALIAS("wmi:" NUC_WMI_WMBC_GUID);
