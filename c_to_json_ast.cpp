#include "slang/ast/Compilation.h"
#include "slang/driver/Driver.h"
#include "slang/ast/ASTSerializer.h"
#include "slang/text/Json.h"

#include <iostream>
#include <fstream>
#include <string>

using namespace slang;
using namespace slang::driver;
using namespace slang::ast;

int main(int argc, char **argv) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <filename>" << std::endl;
        return 1;
    }

    std::string filename = argv[1];
    std::cout << "Chosen SystemVerilog input file: " << filename << std::endl;

    std::ofstream file("output.json", std::ios::trunc);

    Driver driver;
    driver.addStandardArgs();

    if (!driver.parseCommandLine(argc, argv))
        return 1;

    if (!driver.processOptions())
        return 2;

    bool ok = driver.parseAllSources();
    auto compilation = driver.createCompilation();
    ok &= driver.reportCompilation(*compilation, /* quiet */ false);

    // Generate the JSON output file.
    JsonWriter writer;
    writer.setPrettyPrint(true);

    ASTSerializer serializer(*compilation, writer);
    serializer.serialize(compilation->getRoot());

    std::string_view jsonView = writer.view();
    file << jsonView;

    file.close();

    return ok ? 0 : 3;
}
