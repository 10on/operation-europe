// Применяет план из facts (TSV, адреса только в системе Ghidra) к импортированному main.exe
// и пишет TSV со статистикой. Аргументы: <plan.tsv> <out.tsv>
// Строки плана: FUNC<TAB>id<TAB>name<TAB>start<TAB>end|-<TAB>comment ; LABEL<TAB>id<TAB>name<TAB>addr<TAB>comment
// Строки результата: FUNC id name entry min max count size | INSN id addr len mnemonic | LABEL id name addr ok
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

public class ApplyOeFacts extends GhidraScript {
    private Address addr(String text) {
        Address a = currentProgram.getAddressFactory().getAddress(text);
        if (a == null) {
            throw new IllegalArgumentException("bad Ghidra address: " + text);
        }
        return a;
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) {
            throw new IllegalArgumentException("usage: ApplyOeFacts <plan.tsv> <out.tsv>");
        }
        List<String> plan = Files.readAllLines(Paths.get(args[0]), StandardCharsets.UTF_8);
        StringBuilder out = new StringBuilder();
        for (String line : plan) {
            if (line.isEmpty()) continue;
            String[] f = line.split("\t", -1);
            if (f[0].equals("FUNC")) {
                String id = f[1], name = f[2];
                Address start = addr(f[3]);
                AddressSet body = f[4].equals("-") ? null : new AddressSet(start, addr(f[4]));
                // Ограниченное дизассемблирование: только тело функции, без анализа.
                AddressSet region = body != null ? body : new AddressSet(start, start);
                new DisassembleCommand(start, region, true).applyTo(currentProgram, monitor);
                Function fn = currentProgram.getFunctionManager().getFunctionAt(start);
                if (fn == null) {
                    fn = createFunction(start, name);
                }
                if (fn == null) {
                    throw new IllegalStateException("cannot create function " + id + " at " + start);
                }
                fn.setName(name, SourceType.USER_DEFINED);
                if (body != null) {
                    fn.setBody(body);
                }
                currentProgram.getListing().setComment(start, CodeUnit.PLATE_COMMENT, f[5]);
                AddressSet fb = new AddressSet(fn.getBody());
                int count = 0;
                long size = 0;
                StringBuilder insns = new StringBuilder();
                InstructionIterator it = currentProgram.getListing().getInstructions(fb, true);
                while (it.hasNext()) {
                    Instruction ins = it.next();
                    count++;
                    size += ins.getLength();
                    insns.append("INSN\t").append(id).append('\t').append(ins.getAddress())
                         .append('\t').append(ins.getLength()).append('\t').append(ins.getMnemonicString()).append('\n');
                }
                out.append("FUNC\t").append(id).append('\t').append(fn.getName()).append('\t').append(fn.getEntryPoint())
                   .append('\t').append(fb.getMinAddress()).append('\t').append(fb.getMaxAddress())
                   .append('\t').append(count).append('\t').append(size).append('\n');
                out.append(insns);
            } else if (f[0].equals("LABEL")) {
                Address a = addr(f[3]);
                Symbol s = createLabel(a, f[2], true, SourceType.USER_DEFINED);
                currentProgram.getListing().setComment(a, CodeUnit.EOL_COMMENT, f[4]);
                boolean ok = s != null && currentProgram.getMemory().contains(a);
                out.append("LABEL\t").append(f[1]).append('\t').append(f[2]).append('\t').append(a).append('\t').append(ok).append('\n');
            } else {
                throw new IllegalArgumentException("unknown plan row: " + f[0]);
            }
        }
        try (PrintWriter w = new PrintWriter(Files.newBufferedWriter(Paths.get(args[1]), StandardCharsets.UTF_8))) {
            w.print(out);
        }
    }
}
