// SPDX-License-Identifier: GPL-2.0
#ifndef NUC_WMI_LED_LIGHTBAR_H
#define NUC_WMI_LED_LIGHTBAR_H

#if IS_ENABLED(CONFIG_LEDS_CLASS)

#include <linux/init.h>

int  __init nuc_wmi_led_lightbar_setup(void);
void        nuc_wmi_led_lightbar_cleanup(void);

#else

static inline int nuc_wmi_led_lightbar_setup(void)
{
	return 0;
}

static inline void nuc_wmi_led_lightbar_cleanup(void)
{

}

#endif

#endif /* NUC_WMI_LED_LIGHTBAR_H */
