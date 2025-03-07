#include <clang-c/Index.h>
#include <iostream>
#include <fstream>
#include <string>
#include <json/json.h>

void processAST(CXCursor cursor, Json::Value &jsonNode, CXTranslationUnit unit)
{
    CXString kindSpelling = clang_getCursorKindSpelling(cursor.kind);
    CXString name = clang_getCursorSpelling(cursor);

    jsonNode["kind"] = clang_getCString(kindSpelling);
    jsonNode["name"] = clang_getCString(name);

    clang_disposeString(kindSpelling);
    clang_disposeString(name);

    // If it's an IntegerLiteral, extract the literal value
    if (cursor.kind == CXCursor_IntegerLiteral)
    {
        CXSourceRange range = clang_getCursorExtent(cursor);
        CXToken *tokens;
        unsigned numTokens;
        clang_tokenize(unit, range, &tokens, &numTokens);

        if (numTokens > 0)
        {
            CXString tokenSpelling = clang_getTokenSpelling(unit, tokens[0]);
            jsonNode["value"] = clang_getCString(tokenSpelling);
            clang_disposeString(tokenSpelling);
        }

        clang_disposeTokens(unit, tokens, numTokens);
    }

    Json::Value children(Json::arrayValue);
    clang_visitChildren(cursor, [](CXCursor c, CXCursor parent, CXClientData clientData)
                        {
            Json::Value childNode;
            processAST(c, childNode, *(CXTranslationUnit *)clientData);
            ((Json::Value*)clientData)->append(childNode);
            return CXChildVisit_Continue; }, &children);

    if (!children.empty())
        jsonNode["children"] = children;
}

int main(int argc, char *argv[])
{
    if (argc < 2)
    {
        std::cerr << "Usage: " << argv[0] << " <C-file>" << std::endl;
        return 1;
    }

    const char *filename = argv[1];
    CXIndex index = clang_createIndex(0, 0);
    CXTranslationUnit unit = clang_parseTranslationUnit(index, filename, nullptr, 0, nullptr, 0, CXTranslationUnit_None);

    if (!unit)
    {
        std::cerr << "Error parsing file: " << filename << std::endl;
        return 2;
    }

    Json::Value root;
    processAST(clang_getTranslationUnitCursor(unit), root, unit);
    std::ofstream file("output.json");
    file << root.toStyledString();
    file.close();

    clang_disposeTranslationUnit(unit);
    clang_disposeIndex(index);

    std::cout << "AST JSON saved to output.json" << std::endl;
    return 0;
}
