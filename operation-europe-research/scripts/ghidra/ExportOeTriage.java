// Read-only export of 12 existing function definitions beyond the reviewed helper.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.io.PrintWriter;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;

public class ExportOeTriage extends GhidraScript {
 public void run() throws Exception {
  String[] args=getScriptArgs();
  if(args.length!=1) throw new IllegalArgumentException("output path");
  int count=0;
  try(PrintWriter out=new PrintWriter(Files.newBufferedWriter(Paths.get(args[0]),StandardCharsets.UTF_8))){
   out.println("candidate\tentry\tghidra\tfile_offset\tbytes\tasm\tflows");
   FunctionIterator funcs=currentProgram.getFunctionManager().getFunctions(true);
   while(funcs.hasNext() && count<12){
    Function f=funcs.next();
    long file=f.getEntryPoint().subtract(toAddr("1000:0000"))+0x6000L;
    if(file<0xD1C6 || file>0x30000) continue;
    String id=String.format("f%02d",count++);
    InstructionIterator ins=currentProgram.getListing().getInstructions(f.getBody(),true);
    int n=0;
    while(ins.hasNext() && n++<160){
     Instruction i=ins.next();StringBuilder bytes=new StringBuilder();
     for(byte b:i.getBytes()) bytes.append(String.format("%02x",b&255));
     out.println(id+"\t"+f.getEntryPoint()+"\t"+i.getAddress()+"\t"+Long.toHexString(i.getAddress().subtract(toAddr("1000:0000"))+0x6000L)+"\t"+bytes+"\t"+i+"\t"+java.util.Arrays.toString(i.getFlows()));
    }
    out.println(id+"\t"+f.getEntryPoint()+"\tEND\t\t\ttruncated="+ins.hasNext()+"\t");
   }
   if(count==0){
    java.util.TreeSet<ghidra.program.model.address.Address> targets=new java.util.TreeSet<>();
    InstructionIterator all=currentProgram.getListing().getInstructions(true);
    while(all.hasNext()){
     Instruction i=all.next(); if(!i.getFlowType().isCall()) continue;
     for(var a:i.getFlows()){
      long off=a.subtract(toAddr("1000:0000"))+0x6000L;
      if(off>=0xD1C6 && off<0x30000) targets.add(a);
     }
    }
    // Read-only prior analyses do not persist instructions. Fallback candidates:
    // conventional PUSH BP; MOV BP,SP prologue, not proven function boundaries.
    if(targets.isEmpty()) for(int off=0x71c6;off<0x9800;off++){
     var a=toAddr(String.format("1000:%04x",off));
     if((getByte(a)&255)==0x55 && (getByte(a.add(1))&255)==0x8b && (getByte(a.add(2))&255)==0xec) targets.add(a);
    }
    for(var entry:targets){
     if(count>=12) break;
     String id=String.format("f%02d",count++); var a=entry; boolean ended=false;
     for(int n=0;n<64;n++){
      Instruction i=getInstructionAt(a); if(i==null){disassemble(a);i=getInstructionAt(a);}
      if(i==null) break;
      StringBuilder bytes=new StringBuilder(); for(byte b:i.getBytes()) bytes.append(String.format("%02x",b&255));
      out.println(id+"\t"+entry+"\t"+i.getAddress()+"\t"+Long.toHexString(i.getAddress().subtract(toAddr("1000:0000"))+0x6000L)+"\t"+bytes+"\t"+i+"\t"+java.util.Arrays.toString(i.getFlows()));
      if(i.getFlowType().isTerminal()){ended=true;break;}
      if(i.getFallThrough()==null) break;
      a=i.getFallThrough();
     }
     out.println(id+"\t"+entry+"\tEND\t\t\ttruncated="+!ended+"\t");
    }
   }
  }
  println("OE_TRIAGE_FUNCTIONS="+count);
 }
}
