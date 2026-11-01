// Bounded, read-only lookup of one address and its incoming references.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class InspectOeCallers extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) {
            throw new IllegalArgumentException("expected one Ghidra address");
        }
        Address address = currentProgram.getAddressFactory().getAddress(args[0]);
        if (address == null) {
            throw new IllegalArgumentException("unavailable address: " + args[0]);
        }
        Function function = currentProgram.getFunctionManager().getFunctionContaining(address);
        println("OE_ONE_ADDRESS\t" + address);
        println("OE_FUNCTION\t" + (function == null ? "unknown" : function.getEntryPoint() + "\t" + function.getName()));
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(address);
        int total = 0;
        while (refs.hasNext()) {
            Reference ref = refs.next();
            if (total < 20) {
                println("OE_INCOMING\t" + ref.getFromAddress() + "\t" + ref.getReferenceType());
            }
            total++;
        }
        println("OE_INCOMING_COUNT\t" + total + "\tshown=" + Math.min(total, 20) + "\ttruncated=" + (total > 20));
    }
}
