#include <generated/csr.h>
#include <irq.h>
#include <uart.h>

void isr(void);
void isr(void)
{
	unsigned int irqs;
    leds_out_write(1);

    irqs = irq_pending() & irq_getmask();

    if(irqs & (1 << UART_INTERRUPT))
        uart_isr();

    leds_out_write(0);
}
