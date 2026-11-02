CLANG ?= clang
WASM_LD ?= wasm-ld

WASM_CFLAGS = --target=wasm32 -O3 -nostdlib \
  -Wl,--no-entry \
  -Wl,--export-dynamic \
  -Wl,--initial-memory=33554432

all: vm.wasm js/vm_wasm.js

vm.wasm: src/vm.c
	$(CLANG) $(WASM_CFLAGS) src/vm.c -o vm.wasm

js/vm_wasm.js: vm.wasm
	python3 -c 'import base64; b64 = base64.b64encode(open("vm.wasm","rb").read()).decode("ascii"); open("js/vm_wasm.js","w").write("// Pre-compiled ARMv4T + Symbian S60 HLE + 4x xBR/Anime4K WebAssembly Core (Zero Game Data)\nwindow.VM_WASM_BASE64 = \"" + b64 + "\";\n")'

clean:
	rm -f vm.wasm
