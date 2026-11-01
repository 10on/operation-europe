// Find a few exact 16-bit code patterns near filename addresses.
// The far-call target's meaning still requires independent analysis.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;

public class FindOeFileCallSites extends GhidraScript {
    private static final String[][] PATTERNS = {
        {"SCEDATA", "8d1e8c2e"},
        {"HEXMAP.DAT", "8d1e0a2f"},
        {"MSG", "8d1e482f"}
    };

    private static byte[] fromHex(String hex) {
        byte[] out = new byte[hex.length() / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        for (String[] item : PATTERNS) {
            String name = item[0];
            byte[] pattern = fromHex(item[1]);
            int count = 0;
            for (MemoryBlock block : memory.getBlocks()) {
                if (!block.isInitialized() || block.getName().equals("HEADER")) {
                    continue;
                }
                Address cursor = block.getStart();
                while (cursor.compareTo(block.getEnd()) <= 0) {
                    Address found = memory.findBytes(cursor, block.getEnd(), pattern, null, true, monitor);
                    if (found == null) {
                        break;
                    }
                    count++;
                    Instruction lea = currentProgram.getListing().getInstructionAt(found);
                    if (lea == null) {
                        disassemble(found);
                        lea = currentProgram.getListing().getInstructionAt(found);
                    }
                    Address callAddress = found.add(4);
                    Instruction call = currentProgram.getListing().getInstructionAt(callAddress);
                    if (call == null) {
                        disassemble(callAddress);
                        call = currentProgram.getListing().getInstructionAt(callAddress);
                    }
                    println("OE_SITE\t" + name + "\t" + found + "\t" + block.getName()
                        + "\t" + (lea == null ? "<no instruction>" : lea.toString())
                        + "\t" + (call == null ? "<no instruction>" : call.toString()));
                    if (call != null) {
                        for (Address target : call.getFlows()) {
                            println("OE_CALL_TARGET\t" + name + "\t" + found + "\t" + target);
                        }
                    }
                    if (found.equals(block.getEnd())) {
                        break;
                    }
                    cursor = found.add(1);
                }
            }
            println("OE_SITE_COUNT\t" + name + "\t" + count);
        }
    }
}
