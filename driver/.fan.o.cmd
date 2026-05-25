savedcmd_fan.o := gcc -Wp,-MMD,./.fan.o.d -nostdinc -I/usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include -I/usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/generated -I/usr/src/kernels/7.0.8-200.fc44.x86_64/include -I/usr/src/kernels/7.0.8-200.fc44.x86_64/include -I/usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/uapi -I/usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/generated/uapi -I/usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi -I/usr/src/kernels/7.0.8-200.fc44.x86_64/include/generated/uapi -include /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/compiler-version.h -include /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/kconfig.h -include /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/compiler_types.h -D__KERNEL__ -std=gnu11 -fshort-wchar -funsigned-char -fno-common -fno-PIE -fno-strict-aliasing -mno-sse -mno-mmx -mno-sse2 -mno-3dnow -mno-avx -mno-sse4a -fcf-protection=branch -fno-jump-tables -m64 -falign-jumps=1 -falign-loops=1 -mno-80387 -mno-fp-ret-in-387 -mpreferred-stack-boundary=3 -mskip-rax-setup -march=x86-64 -mtune=generic -mno-red-zone -mcmodel=kernel -mstack-protector-guard-reg=gs -mstack-protector-guard-symbol=__ref_stack_chk_guard -Wno-sign-compare -fno-asynchronous-unwind-tables -mindirect-branch=thunk-extern -mindirect-branch-register -mindirect-branch-cs-prefix -mfunction-return=thunk-extern -fno-jump-tables -mharden-sls=all -fpatchable-function-entry=16,16 -fno-delete-null-pointer-checks -O2 -fno-allow-store-data-races -fstack-protector-strong -ftrivial-auto-var-init=zero -fzero-init-padding-bits=all -fno-stack-clash-protection -fdiagnostics-show-context=2 -pg -mrecord-mcount -mfentry -DCC_USING_FENTRY -fno-inline-functions-called-once -fmin-function-alignment=16 -fstrict-flex-arrays=3 -fms-extensions -fno-strict-overflow -fno-stack-check -fconserve-stack -fno-builtin-wcslen -Wall -Wextra -Wundef -Werror=implicit-function-declaration -Werror=implicit-int -Werror=return-type -Werror=strict-prototypes -Wno-format-security -Wno-trigraphs -Wno-frame-address -Wno-address-of-packed-member -Wmissing-declarations -Wmissing-prototypes -Wframe-larger-than=2048 -Wno-main -Wno-type-limits -Wno-dangling-pointer -Wvla-larger-than=1 -Wno-pointer-sign -Wcast-function-type -Wno-unterminated-string-initialization -Wno-array-bounds -Wno-stringop-overflow -Wno-alloc-size-larger-than -Wimplicit-fallthrough=5 -Werror=date-time -Werror=incompatible-pointer-types -Werror=designated-init -Wenum-conversion -Wunused -Wno-unused-but-set-variable -Wno-unused-const-variable -Wno-packed-not-aligned -Wno-format-overflow -Wno-format-truncation -Wno-stringop-truncation -Wno-override-init -Wno-missing-field-initializers -Wno-shift-negative-value -Wno-maybe-uninitialized -Wno-sign-compare -Wno-unused-parameter -g  -fsanitize=bounds-strict -fsanitize=shift    -DMODULE  -DKBUILD_BASENAME='"fan"' -DKBUILD_MODNAME='"nuc_wmi"' -D__KBUILD_MODNAME=nuc_wmi -c -o fan.o fan.c  

source_fan.o := fan.c

deps_fan.o := \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/compiler-version.h \
    $(wildcard include/config/CC_VERSION_TEXT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/kconfig.h \
    $(wildcard include/config/CPU_BIG_ENDIAN) \
    $(wildcard include/config/BOOGER) \
    $(wildcard include/config/FOO) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/compiler_types.h \
    $(wildcard include/config/DEBUG_INFO_BTF) \
    $(wildcard include/config/PAHOLE_HAS_BTF_TAG) \
    $(wildcard include/config/FUNCTION_ALIGNMENT) \
    $(wildcard include/config/CC_HAS_SANE_FUNCTION_ALIGNMENT) \
    $(wildcard include/config/X86_64) \
    $(wildcard include/config/ARM64) \
    $(wildcard include/config/LD_DEAD_CODE_DATA_ELIMINATION) \
    $(wildcard include/config/LTO_CLANG) \
    $(wildcard include/config/HAVE_ARCH_COMPILER_H) \
    $(wildcard include/config/KCSAN) \
    $(wildcard include/config/CC_HAS_ASSUME) \
    $(wildcard include/config/CC_HAS_COUNTED_BY) \
    $(wildcard include/config/FORTIFY_SOURCE) \
    $(wildcard include/config/UBSAN_BOUNDS) \
    $(wildcard include/config/CC_HAS_COUNTED_BY_PTR) \
    $(wildcard include/config/CC_HAS_MULTIDIMENSIONAL_NONSTRING) \
    $(wildcard include/config/UBSAN_INTEGER_WRAP) \
    $(wildcard include/config/CFI) \
    $(wildcard include/config/ARCH_USES_CFI_GENERIC_LLVM_PASS) \
    $(wildcard include/config/CC_HAS_BROKEN_COUNTED_BY_REF) \
    $(wildcard include/config/CC_HAS_ASM_INLINE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/compiler-context-analysis.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/compiler_attributes.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/compiler-gcc.h \
    $(wildcard include/config/ARCH_USE_BUILTIN_BSWAP) \
    $(wildcard include/config/SHADOW_CALL_STACK) \
    $(wildcard include/config/KCOV) \
    $(wildcard include/config/CC_HAS_TYPEOF_UNQUAL) \
  pr.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/printk.h \
    $(wildcard include/config/MESSAGE_LOGLEVEL_DEFAULT) \
    $(wildcard include/config/CONSOLE_LOGLEVEL_DEFAULT) \
    $(wildcard include/config/CONSOLE_LOGLEVEL_QUIET) \
    $(wildcard include/config/EARLY_PRINTK) \
    $(wildcard include/config/PRINTK) \
    $(wildcard include/config/SMP) \
    $(wildcard include/config/PRINTK_INDEX) \
    $(wildcard include/config/DYNAMIC_DEBUG) \
    $(wildcard include/config/DYNAMIC_DEBUG_CORE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/stdarg.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/init.h \
    $(wildcard include/config/MEMORY_HOTPLUG) \
    $(wildcard include/config/HAVE_ARCH_PREL32_RELOCATIONS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/build_bug.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/compiler.h \
    $(wildcard include/config/TRACE_BRANCH_PROFILING) \
    $(wildcard include/config/PROFILE_ALL_BRANCHES) \
    $(wildcard include/config/OBJTOOL) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/generated/asm/rwonce.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/rwonce.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/kasan-checks.h \
    $(wildcard include/config/KASAN_GENERIC) \
    $(wildcard include/config/KASAN_SW_TAGS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/types.h \
    $(wildcard include/config/HAVE_UID16) \
    $(wildcard include/config/UID16) \
    $(wildcard include/config/ARCH_DMA_ADDR_T_64BIT) \
    $(wildcard include/config/PHYS_ADDR_T_64BIT) \
    $(wildcard include/config/64BIT) \
    $(wildcard include/config/ARCH_32BIT_USTAT_F_TINODE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/generated/uapi/asm/types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/asm-generic/types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/int-ll64.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/asm-generic/int-ll64.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/uapi/asm/bitsperlong.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/bitsperlong.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/asm-generic/bitsperlong.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/posix_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/stddef.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/stddef.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/posix_types.h \
    $(wildcard include/config/X86_32) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/uapi/asm/posix_types_64.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/asm-generic/posix_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/kcsan-checks.h \
    $(wildcard include/config/KCSAN_WEAK_MEMORY) \
    $(wildcard include/config/KCSAN_IGNORE_ATOMICS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/stringify.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/kern_levels.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/linkage.h \
    $(wildcard include/config/ARCH_USE_SYM_ANNOTATIONS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/export.h \
    $(wildcard include/config/MODVERSIONS) \
    $(wildcard include/config/GENDWARFKSYMS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/linkage.h \
    $(wildcard include/config/CALL_PADDING) \
    $(wildcard include/config/MITIGATION_RETHUNK) \
    $(wildcard include/config/MITIGATION_RETPOLINE) \
    $(wildcard include/config/MITIGATION_SLS) \
    $(wildcard include/config/FUNCTION_PADDING_BYTES) \
    $(wildcard include/config/UML) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/ibt.h \
    $(wildcard include/config/X86_KERNEL_IBT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/ratelimit_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/bits.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/vdso/bits.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/vdso/const.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/const.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/bits.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/overflow.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/limits.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/limits.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/vdso/limits.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/const.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/param.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/generated/uapi/asm/param.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/param.h \
    $(wildcard include/config/HZ) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/asm-generic/param.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/spinlock_types_raw.h \
    $(wildcard include/config/DEBUG_SPINLOCK) \
    $(wildcard include/config/DEBUG_LOCK_ALLOC) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/spinlock_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/qspinlock_types.h \
    $(wildcard include/config/NR_CPUS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/qrwlock_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/uapi/asm/byteorder.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/byteorder/little_endian.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/byteorder/little_endian.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/swab.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/swab.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/uapi/asm/swab.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/byteorder/generic.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/lockdep_types.h \
    $(wildcard include/config/PROVE_RAW_LOCK_NESTING) \
    $(wildcard include/config/LOCKDEP) \
    $(wildcard include/config/LOCK_STAT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/once_lite.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/dynamic_debug.h \
    $(wildcard include/config/JUMP_LABEL) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/jump_label.h \
    $(wildcard include/config/HAVE_ARCH_JUMP_LABEL_RELATIVE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/cleanup.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/err.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/generated/uapi/asm/errno.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/asm-generic/errno.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/asm-generic/errno-base.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/args.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/jump_label.h \
    $(wildcard include/config/HAVE_JUMP_LABEL_HACK) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/asm.h \
    $(wildcard include/config/KPROBES) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/annotate.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/objtool_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/asm-offsets.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/generated/asm-offsets.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/extable_fixup_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/nops.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/generated/uapi/linux/version.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/bug.h \
    $(wildcard include/config/GENERIC_BUG) \
    $(wildcard include/config/BUG_ON_DATA_CORRUPTION) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/bug.h \
    $(wildcard include/config/DEBUG_BUGVERBOSE) \
    $(wildcard include/config/DEBUG_BUGVERBOSE_DETAILED) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/instrumentation.h \
    $(wildcard include/config/NOINSTR_VALIDATION) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/objtool.h \
    $(wildcard include/config/FRAME_POINTER) \
    $(wildcard include/config/MITIGATION_UNRET_ENTRY) \
    $(wildcard include/config/MITIGATION_SRSO) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/static_call_types.h \
    $(wildcard include/config/HAVE_STATIC_CALL) \
    $(wildcard include/config/HAVE_STATIC_CALL_INLINE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/bug.h \
    $(wildcard include/config/BUG) \
    $(wildcard include/config/GENERIC_BUG_RELATIVE_POINTERS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/panic.h \
    $(wildcard include/config/PANIC_TIMEOUT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/fixp-arith.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/math64.h \
    $(wildcard include/config/ARCH_SUPPORTS_INT128) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/math.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/div64.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/div64.h \
    $(wildcard include/config/CC_OPTIMIZE_FOR_PERFORMANCE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/kernel.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/sysinfo.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/vdso/math64.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/lockdep.h \
    $(wildcard include/config/PROVE_LOCKING) \
    $(wildcard include/config/DEBUG_LOCKING_API_SELFTESTS) \
    $(wildcard include/config/PREEMPT_COUNT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/smp.h \
    $(wildcard include/config/UP_LATE_INIT) \
    $(wildcard include/config/DEBUG_PREEMPT) \
    $(wildcard include/config/CSD_LOCK_WAIT_DEBUG) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/errno.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/errno.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/list.h \
    $(wildcard include/config/LIST_HARDENED) \
    $(wildcard include/config/DEBUG_LIST) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/container_of.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/poison.h \
    $(wildcard include/config/ILLEGAL_POINTER_VALUE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/barrier.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/alternative.h \
    $(wildcard include/config/CALL_THUNKS) \
    $(wildcard include/config/MITIGATION_ITS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/barrier.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/cpumask.h \
    $(wildcard include/config/FORCE_NR_CPUS) \
    $(wildcard include/config/HOTPLUG_CPU) \
    $(wildcard include/config/DEBUG_PER_CPU_MAPS) \
    $(wildcard include/config/CPUMASK_OFFSTACK) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/atomic.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/atomic.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/cmpxchg.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/cpufeatures.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/cmpxchg_64.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/rmwcc.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/atomic64_64.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/atomic/atomic-arch-fallback.h \
    $(wildcard include/config/GENERIC_ATOMIC64) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/atomic/atomic-long.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/atomic/atomic-instrumented.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/instrumented.h \
    $(wildcard include/config/DEBUG_ATOMIC) \
    $(wildcard include/config/DEBUG_ATOMIC_LARGEST_ALIGN) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/kmsan-checks.h \
    $(wildcard include/config/KMSAN) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/bitmap.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/align.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/vdso/align.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/bitops.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/typecheck.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/bitops/generic-non-atomic.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/bitops.h \
    $(wildcard include/config/X86_CMOV) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/bitops/sched.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/arch_hweight.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/bitops/const_hweight.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/bitops/instrumented-atomic.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/bitops/instrumented-non-atomic.h \
    $(wildcard include/config/KCSAN_ASSUME_PLAIN_WRITES_ATOMIC) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/bitops/instrumented-lock.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/bitops/le.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/bitops/ext2-atomic-setbit.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/find.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/string.h \
    $(wildcard include/config/BINARY_PRINTF) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/array_size.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/string.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/string.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/string_64.h \
    $(wildcard include/config/ARCH_HAS_UACCESS_FLUSHCACHE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/fortify-string.h \
    $(wildcard include/config/CC_HAS_KASAN_MEMINTRINSIC_PREFIX) \
    $(wildcard include/config/GENERIC_ENTRY) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/bitmap-str.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/cpumask_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/threads.h \
    $(wildcard include/config/BASE_SMALL) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/gfp_types.h \
    $(wildcard include/config/KASAN_HW_TAGS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/numa.h \
    $(wildcard include/config/NUMA_KEEP_MEMINFO) \
    $(wildcard include/config/NUMA) \
    $(wildcard include/config/HAVE_ARCH_NODE_DEV_GROUP) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/nodemask.h \
    $(wildcard include/config/HIGHMEM) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/minmax.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/nodemask_types.h \
    $(wildcard include/config/NODES_SHIFT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/random.h \
    $(wildcard include/config/VMGENID) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/kernel.h \
    $(wildcard include/config/PREEMPT_VOLUNTARY_BUILD) \
    $(wildcard include/config/PREEMPT_DYNAMIC) \
    $(wildcard include/config/HAVE_PREEMPT_DYNAMIC_CALL) \
    $(wildcard include/config/HAVE_PREEMPT_DYNAMIC_KEY) \
    $(wildcard include/config/PREEMPT_) \
    $(wildcard include/config/DEBUG_ATOMIC_SLEEP) \
    $(wildcard include/config/MMU) \
    $(wildcard include/config/DYNAMIC_FTRACE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/kstrtox.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/log2.h \
    $(wildcard include/config/ARCH_HAS_ILOG2_U32) \
    $(wildcard include/config/ARCH_HAS_ILOG2_U64) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/sprintf.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/trace_printk.h \
    $(wildcard include/config/TRACING) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/instruction_pointer.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/util_macros.h \
    $(wildcard include/config/FOO_SUSPEND) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/wordpart.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/random.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/ioctl.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/generated/uapi/asm/ioctl.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/ioctl.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/asm-generic/ioctl.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/irqnr.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/irqnr.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/sparsemem.h \
    $(wildcard include/config/SPARSEMEM) \
    $(wildcard include/config/X86_PAE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/smp_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/llist.h \
    $(wildcard include/config/ARCH_HAVE_NMI_SAFE_CMPXCHG) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/preempt.h \
    $(wildcard include/config/PREEMPT_RT) \
    $(wildcard include/config/TRACE_PREEMPT_TOGGLE) \
    $(wildcard include/config/PREEMPTION) \
    $(wildcard include/config/PREEMPT_NOTIFIERS) \
    $(wildcard include/config/PREEMPT_NONE) \
    $(wildcard include/config/PREEMPT_VOLUNTARY) \
    $(wildcard include/config/PREEMPT) \
    $(wildcard include/config/PREEMPT_LAZY) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/preempt.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/percpu.h \
    $(wildcard include/config/CC_HAS_NAMED_AS) \
    $(wildcard include/config/USE_X86_SEG_SUPPORT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/percpu.h \
    $(wildcard include/config/HAVE_SETUP_PER_CPU_AREA) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/percpu-defs.h \
    $(wildcard include/config/ARCH_MODULE_NEEDS_WEAK_PER_CPU) \
    $(wildcard include/config/DEBUG_FORCE_WEAK_PER_CPU) \
    $(wildcard include/config/AMD_MEM_ENCRYPT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/thread_info.h \
    $(wildcard include/config/THREAD_INFO_IN_TASK) \
    $(wildcard include/config/ARCH_HAS_PREEMPT_LAZY) \
    $(wildcard include/config/HAVE_ARCH_WITHIN_STACK_FRAMES) \
    $(wildcard include/config/SH) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/restart_block.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/time64.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/vdso/time64.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/time.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/time_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/current.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/cache.h \
    $(wildcard include/config/ARCH_HAS_CACHE_LINE_SIZE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/vdso/cache.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/cache.h \
    $(wildcard include/config/X86_L1_CACHE_SHIFT) \
    $(wildcard include/config/X86_INTERNODE_CACHE_SHIFT) \
    $(wildcard include/config/X86_VSMP) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/thread_info.h \
    $(wildcard include/config/VM86) \
    $(wildcard include/config/X86_FRED) \
    $(wildcard include/config/X86_IOPL_IOPERM) \
    $(wildcard include/config/COMPAT) \
    $(wildcard include/config/IA32_EMULATION) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/page.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/page_types.h \
    $(wildcard include/config/PHYSICAL_START) \
    $(wildcard include/config/PHYSICAL_ALIGN) \
    $(wildcard include/config/DYNAMIC_PHYSICAL_MASK) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/mem_encrypt.h \
    $(wildcard include/config/ARCH_HAS_MEM_ENCRYPT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/mem_encrypt.h \
    $(wildcard include/config/X86_MEM_ENCRYPT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/cc_platform.h \
    $(wildcard include/config/ARCH_HAS_CC_PLATFORM) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/vdso/page.h \
    $(wildcard include/config/PAGE_SHIFT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/page_64_types.h \
    $(wildcard include/config/KASAN) \
    $(wildcard include/config/RANDOMIZE_BASE) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/kaslr.h \
    $(wildcard include/config/RANDOMIZE_MEMORY) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/page_64.h \
    $(wildcard include/config/DEBUG_VIRTUAL) \
    $(wildcard include/config/X86_VSYSCALL_EMULATION) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/mmdebug.h \
    $(wildcard include/config/DEBUG_VM) \
    $(wildcard include/config/DEBUG_VM_IRQSOFF) \
    $(wildcard include/config/DEBUG_VM_PGFLAGS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/range.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/memory_model.h \
    $(wildcard include/config/FLATMEM) \
    $(wildcard include/config/SPARSEMEM_VMEMMAP) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/pfn.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/getorder.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/cpufeature.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/processor.h \
    $(wildcard include/config/X86_VMX_FEATURE_NAMES) \
    $(wildcard include/config/X86_USER_SHADOW_STACK) \
    $(wildcard include/config/X86_DEBUG_FPU) \
    $(wildcard include/config/PARAVIRT_XXL) \
    $(wildcard include/config/CPU_SUP_AMD) \
    $(wildcard include/config/XEN) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/processor-flags.h \
    $(wildcard include/config/MITIGATION_PAGE_TABLE_ISOLATION) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/uapi/asm/processor-flags.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/math_emu.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/ptrace.h \
    $(wildcard include/config/PARAVIRT) \
    $(wildcard include/config/X86_DEBUGCTLMSR) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/segment.h \
    $(wildcard include/config/XEN_PV) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/uapi/asm/ptrace.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/uapi/asm/ptrace-abi.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/paravirt-base.h \
    $(wildcard include/config/PARAVIRT_SPINLOCKS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/proto.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/uapi/asm/ldt.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/uapi/asm/sigcontext.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/cpuid/api.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/cpuid/types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/paravirt.h \
    $(wildcard include/config/DEBUG_ENTRY) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/paravirt_types.h \
    $(wildcard include/config/ZERO_CALL_USED_REGS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/desc_defs.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/pgtable_types.h \
    $(wildcard include/config/X86_INTEL_MEMORY_PROTECTION_KEYS) \
    $(wildcard include/config/MEM_SOFT_DIRTY) \
    $(wildcard include/config/HAVE_ARCH_USERFAULTFD_WP) \
    $(wildcard include/config/PGTABLE_LEVELS) \
    $(wildcard include/config/PROC_FS) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/pgtable_64_types.h \
    $(wildcard include/config/DEBUG_KMAP_LOCAL_FORCE_MAP) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/nospec-branch.h \
    $(wildcard include/config/CALL_THUNKS_DEBUG) \
    $(wildcard include/config/MITIGATION_CALL_DEPTH_TRACKING) \
    $(wildcard include/config/MITIGATION_IBPB_ENTRY) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/static_key.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/msr-index.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/unwind_hints.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/orc_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/GEN-for-each-reg.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/frame.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/special_insns.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/irqflags.h \
    $(wildcard include/config/TRACE_IRQFLAGS) \
    $(wildcard include/config/IRQSOFF_TRACER) \
    $(wildcard include/config/PREEMPT_TRACER) \
    $(wildcard include/config/DEBUG_IRQFLAGS) \
    $(wildcard include/config/TRACE_IRQFLAGS_SUPPORT) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/irqflags_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/irqflags.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/fpu/types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/vmxfeatures.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/vdso/processor.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/shstk.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/personality.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/uapi/linux/personality.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/generated/asm/cpufeaturemasks.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/asm-generic/thread_info_tif.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/smp.h \
    $(wildcard include/config/DEBUG_NMI_SELFTEST) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/arch/x86/include/asm/cpumask.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/mutex.h \
    $(wildcard include/config/DEBUG_MUTEXES) \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/spinlock_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/rwlock_types.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/osq_lock.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/debug_locks.h \
  /usr/src/kernels/7.0.8-200.fc44.x86_64/include/linux/mutex_types.h \
    $(wildcard include/config/MUTEX_SPIN_ON_OWNER) \
  ec.h \
  fan.h \
  util.h \

fan.o: $(deps_fan.o)

$(deps_fan.o):
