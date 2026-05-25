#ifndef NUC_WMI_LAPTOP_FAN_H
#define NUC_WMI_LAPTOP_FAN_H

#include <linux/types.h>

/* ========================================================================== */

#define FAN_MAX_PWM        200
#define FAN_CTRL_MAX_LEVEL   7
#define FAN_CTRL_LEVEL(level) (128 + (level))

/* ========================================================================== */

int nuc_wmi_fan_get_rpm(uint8_t fan_index);
int nuc_wmi_fan_query_abnorm(void);
int nuc_wmi_fan_get_pwm(uint8_t fan_index);
int nuc_wmi_fan_set_pwm(uint8_t fan_index, uint8_t pwm);
int nuc_wmi_fan_get_temp(uint8_t fan_index);
int nuc_wmi_fan_get_mode(void);
int nuc_wmi_fan_set_mode(uint8_t mode);

#endif /* NUC_WMI_LAPTOP_FAN_H */
