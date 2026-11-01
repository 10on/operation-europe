// Bounded read-only-session startup export; never save the Ghidra program.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.io.PrintWriter;
public class InspectOeStartup extends GhidraScript {
    public void run() throws Exception {
        String[] a=getScriptArgs();
        Address p=toAddr(a[1]);
        long header=Long.decode(a[2]);
        try(PrintWriter out=new PrintWriter(Files.newBufferedWriter(Paths.get(a[0]),StandardCharsets.UTF_8))){
            out.println("ghidra\tfile_offset\tbytes_relocated\tasm");
            for(int i=0;i<180;i++){
                Instruction ins=getInstructionAt(p);
                if(ins==null){disassemble(p);ins=getInstructionAt(p);}
                if(ins==null){out.println("MISSING\t"+p);break;}
                StringBuilder raw=new StringBuilder();
                for(byte b:ins.getBytes())raw.append(String.format("%02x",b&255));
                out.println(p+"\t"+String.format("0x%x",header+p.subtract(toAddr("1000:0000")))+"\t"+raw+"\t"+ins);
                if(ins.getMnemonicString().equals("RET")) break;
                p=p.add(ins.getLength());
            }
        }
        println("OE_STARTUP_EXPORT "+currentProgram.getName()+" "+a[0]);
    }
}
