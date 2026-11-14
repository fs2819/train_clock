# Pi boot partition backup

Known-good copies of the FAT32 boot partition files from `fsheehan-pi`.
**No secrets here** — `network-config` and `user-data` hold Wi-Fi credentials
and a password hash, so they are deliberately not committed.

`cmdline.txt` was found truncated to 0 bytes on 2026-08-19 after the Pi was
unplugged while the boot partition was being written. With it empty the kernel
gets no `root=`, never mounts the root filesystem, and the Pi appears to boot
(ACT LED flickering) while never reaching userspace — no Wi-Fi, no service,
hands frozen.

Refreshed 2026-09-18 after reflashing onto a clean image. `/boot/firmware` is now mounted read-only on the Pi (see /etc/fstab), so this truncation should not recur.

Refreshed 2026-11-14: `cmdline.txt` loads `dwc2,g_ether` and `config.txt` sets
`dtoverlay=dwc2` under `[all]`, giving a USB-ethernet link on the inner USB port
(micro-USB data cable to a Mac, then `ssh fsheehan-pi.local`) when Wi-Fi is down.

## Wi-Fi profiles on the root partition

NetworkManager rewrites every `/etc/netplan/90-NM-*.yaml` about 25–40 s after
each boot. Losing power in that window leaves them 0 bytes and the Pi comes up
with no Wi-Fi profile (happened 2026-09-18 and 2026-10-05). `netplan-repair.service`
runs before NetworkManager and restores any empty or missing file from
`/var/backups/netplan-good/`; after changing Wi-Fi networks, refresh that copy:
`sudo cp -p /etc/netplan/90-NM-*.yaml /var/backups/netplan-good/`.
Do not `chattr +i` these files: NetworkManager aborts (SIGABRT) when it cannot
rewrite them, taking Wi-Fi and the USB link down with it.

To restore: put the SD card in a Mac and copy these over the ones on
`/Volumes/bootfs`. `cmdline.txt` MUST stay a single line.
