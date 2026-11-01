// Read-only metadata check for an already imported Operation Europe program.
// Run with analyzeHeadless -process <name> -readOnly -noanalysis -postScript InspectOeProgram.java.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import java.util.Iterator;

public class InspectOeProgram extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("OE_PROGRAM\t" + currentProgram.getName());
        println("OE_EXECUTABLE_PATH\t" + currentProgram.getExecutablePath());
        println("OE_EXECUTABLE_FORMAT\t" + currentProgram.getExecutableFormat());
        println("OE_LANGUAGE\t" + currentProgram.getLanguage().getLanguageID());
        println("OE_COMPILER_SPEC\t" + currentProgram.getCompilerSpec().getCompilerSpecID());
        println("OE_IMAGE_BASE\t" + currentProgram.getImageBase());

        int entryCount = 0;
        Iterator<Address> entries = currentProgram.getSymbolTable().getExternalEntryPointIterator();
        while (entries.hasNext()) {
            println("OE_ENTRY\t" + entries.next());
            entryCount++;
        }
        println("OE_ENTRY_COUNT\t" + entryCount);

        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            println("OE_BLOCK\t" + block.getName() + "\t" + block.getStart() + "\t"
                + block.getEnd() + "\t" + block.getSize() + "\t"
                + block.isInitialized() + "\t" + block.isOverlay());
        }
    }
}
