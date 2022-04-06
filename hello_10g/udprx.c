// UDP verification and benchmark tool
// build with `make udprx`

#include <stdio.h>
#include <inttypes.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <arpa/inet.h>
#include <time.h>

#define GBYTE (1024 * 1024 * 1024)

int print_per_rx_packet = 0;

/* MTU = 9710, subtract 28 octets for IP and UDP header? */
#define NEXT(x) ((x) * 3 + 1)
static unsigned udp_handle(char *data, unsigned data_len)
{
	static uint64_t tot_received = 0;
	static uint64_t tot_bytes;
	static uint64_t last_tot_bytes;
	static time_t last_ts = 0;
	unsigned fail = 0;

	tot_received++;
	tot_bytes += data_len;

	if ((data_len % 8) > 0) {
		printf("wrong length: %d, partial packet?\n", data_len);
		fail++;
	}
	unsigned n_words = data_len / 8;
	uint64_t *words = (uint64_t *)data;  // spicy!
	uint64_t key = words[0];
	uint64_t sta = key;

	static uint64_t last_key = -1;
	static uint64_t tot_dropped = 0;
	uint64_t n_dropped = key - last_key - 1;
	if (last_key != -1 && n_dropped > 0) {
		tot_dropped += n_dropped;
	}
	last_key = key;

	time_t ts = time(NULL);
	if (ts - last_ts > 1) {
		printf(
			"%4.1f GB (%4.1f GB), dropped %lu / %lu packets (%.1e)\n",
			(float)(tot_bytes - last_tot_bytes) / GBYTE,
			(float)tot_bytes / GBYTE,
			tot_dropped,
			tot_received,
			(float)tot_dropped / tot_received
		);
		last_ts = ts;
		last_tot_bytes = tot_bytes;
	}

	if (1) for (unsigned i=0; i<n_words; i++) {
		uint64_t want_d = sta ^ i;
		if (words[i] != want_d) {
			printf("words[%2u] = %016x != %016x\n", i, words[i], want_d);
			// printf("data[%2u]: %2.2x, sta: %2.2x, key: %2.2x\n", u, want_d, sta, key);
			fail++;
		}
		sta = NEXT(sta);
	}
	if (fail || print_per_rx_packet) printf("udp_handle  length=%4u  key=%lu  ", data_len, key);
	if (fail) {
		printf("%d FAIL\n", fail);
	} else {
		if (print_per_rx_packet) printf("PASS\n");
	}
	return fail;
}

static void primary_loop(int usd, unsigned npack, unsigned juggle)
{
	fd_set fds_r, fds_e;
	struct sockaddr sa_xmit;
	unsigned int sa_xmit_len;
	struct timeval to;
	int i, pack_len;
	int debug1 = 0;
	unsigned probes_sent = 0, probes_recv = 0, probes_fail = 0;
	unsigned timeouts = 0;
	static char incoming[15000];
	sa_xmit_len = sizeof(sa_xmit);
	for (;npack == 0 || probes_recv < npack;) {
		FD_ZERO(&fds_r);
		FD_SET(usd, &fds_r);
		FD_ZERO(&fds_e);
		FD_SET(usd, &fds_e);
		to.tv_sec = 1;
		to.tv_usec = 0;
		i = select(usd + 1, &fds_r, NULL, &fds_e, &to);
		// Wait on read or error
		if (debug1) printf("select returns %d\n", i);
		if (i < 0) {
			if (debug1) printf(" error\n");
			if (errno != EINTR) perror("select");
			else printf("EINTR\n");
			continue;
		} else if (i == 0) {
			++timeouts;
			continue;
		} else if (!FD_ISSET(usd, &fds_r)) {
			++timeouts;
			continue;
		}
		if (debug1) printf(" receiving\n");
		pack_len = recvfrom(
			usd, incoming, sizeof(incoming), 0, &sa_xmit, &sa_xmit_len
		);
		if (pack_len < 0) {
			perror("recvfrom");
		} else if (pack_len > 0 && (unsigned)pack_len < sizeof(incoming)) {
			++probes_recv;
			if (udp_handle(incoming, pack_len) > 0)
				++probes_fail;
		} else {
			printf("Ooops.  pack_len = %d\n", pack_len);
			fflush(stdout);
			break;
		}
	}
	printf("%u packets sent, %u received, %u failed, %u timeouts\n",
		probes_sent, probes_recv, probes_fail, timeouts);
}

static void setup_receive(int usd, unsigned int interface, short port)
{
	struct sockaddr_in sa_rcvr;
	memset(&sa_rcvr,0,sizeof sa_rcvr);
	sa_rcvr.sin_family=AF_INET;
	sa_rcvr.sin_addr.s_addr=htonl(interface);
	sa_rcvr.sin_port=htons(port);
	if(bind(usd,(struct sockaddr *) &sa_rcvr,sizeof sa_rcvr) == -1) {
		perror("bind");
		fprintf(stderr,"could not bind to udp port %d\n",port);
		exit(1);
	}
	uint64_t receive_buf_size = 1 * GBYTE;
	setsockopt(usd, SOL_SOCKET, SO_RCVBUF, &receive_buf_size, sizeof(receive_buf_size));
}

int main(int argc, char *argv[])
{
	int usd, npack;
	unsigned short port_number;

	if (argc < 2) {
		fprintf(
			stderr,
			"Verify and benchmark incoming UDP stream\n"
			"Usage: %s udp_port_number [number_of_packets] [debug]\n",
			argv[0]
		);
		exit(1);
	}

	port_number = atoi(argv[1]);

	npack = 0;
	if (argc >= 3)
		npack = atoi(argv[2]);

	if (argc >= 4)
		print_per_rx_packet = atoi(argv[3]) > 0;

	usd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
	if (usd == -1) {
		perror("socket");
		exit(1);
	}

	setup_receive(usd, INADDR_ANY, port_number);
	primary_loop(usd, npack, 0);
	close(usd);
	return 0;
}
