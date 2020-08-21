
	.file	"hello.c"
	.def	___main;	.scl	2;	.type	32;	.endef
	.section .rdata,"dr"
LC0:
	.ascii "%d*%d=%d	\0"
LC1:
	.ascii "\n\0"
	.text
	.globl	_main
	.def	_main; .scl	2;	.type	32;	.endef
_main:
LFB10:
	.cfi_startproc
	pushl	%ebp
	.cfi_def_cfa_offset 8
	.cfi_offset 5, -8
	movl	%esp, %ebp
	.cfi_def_cfa_register 5
	andl	$-16, %esp
	subl	$48, %esp
	call	___main
	movl	$1, 44(%esp)
L1:
	movl	44(%esp), %eax
	cmpl	$10, %eax
	jl L2
	jmp L3
L2:
	movl	$1, 40(%esp)
L4:
	movl	40(%esp), %eax
	cmpl	$10, %eax
	jl L5
	jmp L6
L5:
	movl	44(%esp), %eax
	imull	40(%esp), %eax
	movl	%eax, 36(%esp)
	movl	36(%esp), %eax
	movl	%eax, 12(%esp)
	movl	40(%esp), %eax
	movl	%eax, 8(%esp)
	movl	44(%esp), %eax
	movl	%eax, 4(%esp)
	movl	$LC0, (%esp)
	call	_printf
	movl	40(%esp), %eax
	addl	$1, %eax
	movl	%eax, 32(%esp)
	movl	32(%esp), %eax
	movl	%eax, 40(%esp)
	jmp L4
L6:
	movl	$LC1, (%esp)
	call	_printf
	movl	44(%esp), %eax
	addl	$1, %eax
	movl	%eax, 28(%esp)
	movl	28(%esp), %eax
	movl	%eax, 44(%esp)
	jmp L1
L3:
	leave
	.cfi_restore 5
	.cfi_def_cfa 4, 4
	ret
	.cfi_endproc
LFE10:
	.ident	"BWCC: (Nuke666.cn BWCC-0.0.1) 6.3.0"
	.def	_printf;	.scl	2;	.type	32;	.endef
