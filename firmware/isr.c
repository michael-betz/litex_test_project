#include <generated/csr.h>
#include <irq.h>
#include <uart.h>

extern void periodic_isr(void);

void led_test(void);
void led_test(void)
{
    static unsigned i=0;
    leds_out_write((i++&1) + 1);
}

void isr(void);
void isr(void)
{
	unsigned int irqs;
    led_test();
    // leds_out_write(1);
    irqs = irq_pending() & irq_getmask();

    if(irqs & (1 << UART_INTERRUPT))
        uart_isr();


}
