// Search initialized Ghidra memory for selected DOS filenames and existing xrefs.
// This script does not change the program or export game bytes.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;

public class FindOeFileNames extends GhidraScript {
    private static final String[] NAMES = {"SCEDATA", "HEXMAP.DAT", "MSG", "EMSG"};

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        for (String name : NAMES) {
            byte[] pattern = name.getBytes(StandardCharsets.US_ASCII);
            int matches = 0;
            for (MemoryBlock block : memory.getBlocks()) {
                if (!block.isInitialized() || block.getName().equals("HEADER")) {
                    continue;
                }
                Address cursor = block.getStart();
                while (cursor.compareTo(block.getEnd()) <= 0 && matches < 24) {
                    Address found = memory.findBytes(cursor, block.getEnd(), pattern, null, true, monitor);
                    if (found == null) {
                        break;
                    }
                    matches++;
                    ReferenceIterator references = currentProgram.getReferenceManager().getReferencesTo(found);
                    ArrayList<Reference> refs = new ArrayList<>();
                    while (references.hasNext()) {
                        refs.add(references.next());
                    }
                    println("OE_MATCH\t" + name + "\t" + found + "\t" + block.getName()
                        + "\t" + refs.size());
                    for (int i = 0; i < refs.size() && i < 16; i++) {
                        Reference ref = refs.get(i);
                        Address from = ref.getFromAddress();
                        Function function = currentProgram.getFunctionManager().getFunctionContaining(from);
                        println("OE_REF\t" + name + "\t" + found + "\t" + from + "\t"
                            + ref.getReferenceType() + "\t"
                            + (function == null ? "<none>" : function.getName()));
                    }
                    if (found.equals(block.getEnd())) {
                        break;
                    }
                    cursor = found.add(1);
                }
            }
            println("OE_MATCH_COUNT\t" + name + "\t" + matches);
        }
    }
}
