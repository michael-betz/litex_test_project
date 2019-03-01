// lm32: everything works as expected, no surprises
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <console.h>
#include <generated/csr.h>

static void busy_wait(unsigned int ds)
{
	timer0_en_write(0);
	timer0_reload_write(0);
	timer0_load_write(SYSTEM_CLOCK_FREQUENCY/10*ds);
	timer0_en_write(1);
	timer0_update_value_write(1);
	while(timer0_value_read()) timer0_update_value_write(1);
}

static char *readstr(void)
{
	// FIXME picorv32: assigning to `ptr` freezes the CPU, ok on vexriscv

	char c[2];
	static char s[64];
	static int ptr = 0;

	if(readchar_nonblock()) {
		c[0] = readchar();
		c[1] = 0;
		switch(c[0]) {
			case 0x7f:
			case 0x08:
				if(ptr > 0) {
					ptr--;
					putsnonl("\x08 \x08");
				}
				break;
			case 0x07:
				break;
			case '\r':
			case '\n':
				s[ptr] = 0x00;
				putsnonl("\n");
				ptr = 0;
				return s;
			default:
				if(ptr >= (sizeof(s) - 1))
					break;
				putsnonl(c);
				s[ptr] = c[0];
				ptr++;
				break;
		}
	}

	return NULL;
}

static char *get_token(char **str)
{
	char *c, *d;

	c = (char *)strchr(*str, ' ');
	if(c == NULL) {
		d = *str;
		*str = *str+strlen(*str);
		return d;
	}
	*c = 0;
	d = *str;
	*str = c+1;
	return d;
}

static void prompt(void)
{
	// FIXME printf gets vexriscv stuck in ISR
	printf("RUNTIME>");
	// putsnonl("RUNTIME>");
}

static void help(void)
{
	puts("Available commands:");
	puts("help                            - this command");
	puts("reboot                          - reboot CPU");
}

static void reboot(void)
{
	printf("Would be doing a reboot now if I could ... \n");
	// asm("J 0");
}

static void console_service(void)
{
	char *str;
	char *token;
	// str = readstr();
	// if(str == NULL) return;
	// FIXME `get_token` freezes the CPU (picorv32 & vexriscv)
	token = get_token(&str);
	// token = str;
	// FIXME freeze on picorv32 (ISR stops triggering as well)
	if(strcmp(token, "help") == 0)
		help();
	// FIXME main.c:92:(.text.startup+0x144): relocation truncated to fit: R_RISCV_JAL against `*UND*' (picorv32 & vexriscv)
	else if(strcmp(token, "reboot") == 0)
		reboot();
	prompt();
}

// char gVar1 = 0;
// int gVar2 = 0;
// int gVar3 = 0;
int main(void)
{
	irq_setmask(0);
	irq_setie(1);
	uart_init();

	puts("\nLab004xxx - CPU testing software built "__DATE__" "__TIME__"\n");
	help();
	prompt();

	unsigned i=0;
	while(1) {
		printf("gVar: %d\n", 2);
		// FIXME vexriscv does output `test `, should be `test 0\n`
		printf("test %d,  strcmp: %d\n", i++, strcmp("help", "help "));
		// FIXME vexriscv seems to require this, else freezes
		busy_wait(1);
		// console_service();
	}

	return 0;
}
