// Bounded disassembly of one far-call target in the existing main.exe import.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;

public class InspectOeTarget extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String requested = args.length > 0 ? args[0] : "1977:000e";
        int maxInstructions = args.length > 1 ? Integer.parseInt(args[1]) : 48;
        if (maxInstructions < 1 || maxInstructions > 256) {
            throw new IllegalArgumentException("instruction limit must be 1..256");
        }
        Address address = currentProgram.getAddressFactory().getAddress(requested);
        if (address == null) {
            throw new IllegalStateException("target address is unavailable: " + requested);
        }
        disassemble(address);
        for (int i = 0; i < maxInstructions; i++) {
            Instruction instruction = currentProgram.getListing().getInstructionAt(address);
            if (instruction == null) {
                disassemble(address);
                instruction = currentProgram.getListing().getInstructionAt(address);
            }
            if (instruction == null) {
                println("OE_TARGET_END\t" + address + "\t<no instruction>");
                break;
            }
            println("OE_TARGET_INSN\t" + instruction.getAddress() + "\t" + instruction.toString());
            String mnemonic = instruction.getMnemonicString();
            if (mnemonic.startsWith("RET") || mnemonic.equals("JMP") || mnemonic.equals("JMPF")) {
                println("OE_TARGET_END\t" + instruction.getAddress() + "\tbranch-or-return\ttruncated=false\ttotal_count=" + (i + 1));
                break;
            }
            address = address.add(instruction.getLength());
            if (i + 1 == maxInstructions) {
                println("OE_TARGET_END\t" + address + "\tlimit\ttruncated=true\ttotal_count>= " + maxInstructions);
            }
        }
    }
}
