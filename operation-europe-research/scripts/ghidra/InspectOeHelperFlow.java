// TASK-008: bounded CFG, following jumps but never entering callees.
// Fixed scope is the helper preceding the TASK-007A function, not a general analyzer.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayDeque;
import java.util.HashSet;

public class InspectOeHelperFlow extends GhidraScript {
    @Override public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1 && args.length != 3) throw new IllegalArgumentException("output TSV [start limit]");
        Address start = toAddr(args.length==3 ? args[1] : "16db:00b4");
        Address limit = toAddr(args.length==3 ? args[2] : "16db:0378");
        ArrayDeque<Address> queue = new ArrayDeque<>();
        HashSet<Address> visited = new HashSet<>();
        queue.add(start);
        // Two targets decoded independently from the observed CS:[BX+0122] table.
        if(args.length==1){queue.add(toAddr("16db:00c4"));queue.add(toAddr("16db:00ee"));}
        int count = 0;
        try (PrintWriter out = new PrintWriter(Files.newBufferedWriter(Paths.get(args[0]), StandardCharsets.UTF_8))) {
            out.println("kind\tghidra\tfile_offset\tbytes_or_target\tasm");
            while (!queue.isEmpty() && count < 256 && !monitor.isCancelled()) {
                Address a = queue.removeFirst();
                if (!visited.add(a)) continue;
                if (a.subtract(start) < 0 || a.subtract(limit) >= 0) {
                    out.println("outside\t" + a + "\t\t\t"); continue;
                }
                Instruction ins = getInstructionAt(a);
                if (ins == null) { disassemble(a); ins = getInstructionAt(a); }
                if (ins == null) { out.println("missing\t" + a + "\t\t\t"); continue; }
                StringBuilder raw = new StringBuilder();
                for (byte b : ins.getBytes()) raw.append(String.format("%02x", b & 255));
                long file = 0x6000L + a.subtract(toAddr("1000:0000"));
                out.println("insn\t" + a + "\t" + String.format("0x%x",file) + "\t" + raw + "\t" + ins);
                count++;
                if (ins.getFlowType().isCall()) {
                    for (Address target : ins.getFlows()) out.println("call\t" + a + "\t\t" + target + "\t");
                } else {
                    for (Address target : ins.getFlows()) queue.add(target);
                    if (ins.getFlowType().isComputed()) out.println("computed\t" + a + "\t\t\t" + ins);
                }
                if (ins.getFallThrough() != null) queue.add(ins.getFallThrough());
            }
            out.println("summary\t\t\t" + count + "\tqueue_remaining=" + queue.size() + ";cancelled=" + monitor.isCancelled());
        }
        println("OE_HELPER_EXPORTED count=" + count + " pending=" + queue.size());
    }
}
