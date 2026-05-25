savedcmd_nuc_wmi.o := ld -m elf_x86_64 -z noexecstack --no-warn-rwx-segments   -r -o nuc_wmi.o @nuc_wmi.mod  ; /usr/src/kernels/7.0.8-200.fc44.x86_64/tools/objtool/objtool --hacks=jump_label --hacks=noinstr --hacks=skylake --ibt --orc --retpoline --rethunk --sls --static-call --uaccess --prefix=16  --link  --module nuc_wmi.o

nuc_wmi.o: $(wildcard /usr/src/kernels/7.0.8-200.fc44.x86_64/tools/objtool/objtool)
