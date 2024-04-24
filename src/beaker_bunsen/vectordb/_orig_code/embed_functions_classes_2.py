# -*- coding: utf-8 -*-
import ast
import glob
import json
from .embed_utils import RecursiveCharacterTextSplitter,count_words,start_chromadb
import os


def get_full_module_name(file_path, code_directory,code_repo_name='mira'):
    """
    Converts a file path to its full module name, based on the project root.
    
    :param file_path: Absolute or relative file path of the Python module.
    :param project_root: The root directory of the project.
    :return: Full module name as a string.
    """
    # Ensure project_root ends with a path separator for consistent removal
    project_root = os.path.join(code_directory, '')
    relative_path = os.path.relpath(file_path, project_root)
    module_name = os.path.splitext(relative_path)[0].replace(os.sep, '.')
    module_name=f'{code_repo_name}.'+module_name
    return module_name

def extract_function_and_class_source_and_docstrings(file_path,code_directory,code_repo_name='mira'):
    """Extracts function and class (including methods) source code, their docstrings, and module from a given Python file."""
    module_name = get_full_module_name(file_path,code_directory,code_repo_name='mira')
    with open(file_path, 'r') as file:
        file_contents = file.read()
        source_lines = file_contents.splitlines()
        node = ast.parse(file_contents)
        items = []

        for item in node.body:
            if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                # Extract function details including module name
                items.append(extract_item_details(item, source_lines, "function", module_name))
            elif isinstance(item, ast.ClassDef):
                # Extract class details including module name
                class_info = extract_item_details(item, source_lines, "class", module_name)
                items.append(class_info)

        return items

def extract_item_details(item, source_lines, kind, module_name):
    """Extracts details of a function or class item including module name."""
    start_lineno = item.lineno
    end_lineno = getattr(item, 'end_lineno', start_lineno)
    item_source_lines = source_lines[start_lineno-1:end_lineno]
    item_source = '\n'.join(item_source_lines)
    docstring = ast.get_docstring(item)
    full_name = f"{module_name}.{item.name}"
    if kind == "function" or kind == "class":
        return (full_name, item_source, docstring)
    else:
        return None 
    

def process_directory(directory,max_lines=40,chunk_size=1500,library_name="mira"):
    """Extracts functions and their docstrings in a repository."""
    documents = []
    #https://github.com/DARPA-ASKEM/beaker-elwood/blob/main/src/beaker_elwood_context/agent.py
    #https://github.com/langchain-ai/langchain/blob/6e90b7a91bba16d84689d07d1016a941eddf4f64/templates/rag-codellama-fireworks/rag_codellama_fireworks/chain.py#L33
    all_functions = {}
    files=glob.glob(directory+'/**',recursive=True)
    for file in files:
        if file.endswith('.py'):
            functions_classes=extract_function_and_class_source_and_docstrings(file,directory,library_name)
            #functions = extract_function_source_and_docstring(file)
            if functions_classes:
                print_functions=[{'name':functions_class[0],'source_code':functions_class[1],'doc_string':functions_class[2]} for functions_class in functions_classes]
                documents.extend([(json.dumps(print_function),{'file_path':file,'name':print_function['name']}) for print_function in print_functions])

    return documents



        
def embed_functions_and_classes(function_dir,collection_name="function_index",library_name="mira"):
    #get functions and classes from all .py files in dir
    documents= process_directory(function_dir,library_name=library_name)
    
    collection = start_chromadb(collection_name=collection_name)
    
    #check if already there
    metadatas=collection.get()['metadatas']
    functions_or_classes_names=[metadata['name'] for metadata in metadatas]
    print(functions_or_classes_names)
    documents=[doc for doc in documents if doc[1]['name'] not in functions_or_classes_names]  
    
    #realign doc content for input into chroma
    document_texts=[doc[0] for doc in documents]
    metadatas=[doc[1] for doc in documents]
    ids=[metadata['name'] for metadata in metadatas]
    
    #check for redundant functions
    seen = {}
    unique_indexes = []

    for index, value in enumerate(ids):
        if value not in seen:
            seen[value] = index
            unique_indexes.append(index)
            
    #filter out redundant
    document_texts = [document_texts[index] for index in unique_indexes]
    metadatas = [metadatas[index] for index in unique_indexes]
    ids = [ids[index] for index in unique_indexes]
    
    # Add to ChromaDB collection
    try:
        collection.add(
        documents=document_texts,
        metadatas=metadatas,
        ids=ids
        )
    except Exception as e:
        print('unable to add to collection: {e}')
        

def query_functions_classes(query,collection_name="function_index",path="/bio_context/chromadb_functions",n_results=5):
    collection = start_chromadb(collection_name=collection_name,path=path)
    result = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    text=''
    for i in range(len(result['ids'][0])):
        text+=f"Information related to for function or class: {result['ids'][0][i]} :\n{result['documents'][0][i]}\n"

    return text
