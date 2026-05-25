savedcmd_ite8291r3.mod := printf '%s\n'   ite8291r3.o | awk '!x[$$0]++ { print("./"$$0) }' > ite8291r3.mod
