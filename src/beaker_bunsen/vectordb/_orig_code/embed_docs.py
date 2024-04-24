import inspect
import openai
import pkgutil
import importlib
import os
import chromadb  # Assuming ChromaDB has a Python SDK
import tiktoken
import time
import json
from tqdm import tqdm
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List,Union
import tenacity
#DONE: need to add classes themselves. Only class functions are exposed right now.
#TODO: add examples to returned values? Get examples from searching the repo?
from typing import _SpecialGenericAlias

def start_chromadb(docker=False):
    import chromadb
    if docker:
        #Initialize ChromaDB client and create a collection
        client = chromadb.HttpClient(host='localhost', port=8000)
    else:
        #chroma_client = chromadb.PersistentClient(path="./chromabd_functions")
        chroma_client = chromadb.PersistentClient(path="/bio_context/chromadb_functions")
    
    collection = chroma_client.get_or_create_collection(name="full")
    
    openai.api_key = os.environ['OPENAI_API_KEY']
    return collection

def get_function_info(module, item, full_name):
    library_base_path = os.path.dirname(inspect.getfile(module))  # Get the base path of the library
    try:
        # Check if the item's file path starts with the library's base path
        item_file_path = inspect.getfile(item)
        if not item_file_path.startswith(library_base_path):
            print(f"Skipping {full_name}: Not part of the library.")
            return

        docstring = item.__doc__ or ''
        source_code = inspect.getsource(item)

    except Exception as e:
        print(f"Skipping {full_name}: {e}")
        
    return docstring,source_code

def get_class_info(module, item, full_name):
    library_base_path = os.path.dirname(inspect.getfile(module))  # Get the base path of the library
    try:
        # Check if the item's file path starts with the library's base path
        item_file_path = inspect.getfile(item)
        if not item_file_path.startswith(library_base_path):
            print(f"Skipping {full_name}: Not part of the library.")
            return
        docstring = item.__doc__ or ''
        source_code = inspect.getsource(item)
        return None
    except Exception as e:
        print(f"Skipping {full_name}: {e}")   
        
    return docstring,source_code



def process_submodule(module, submodule,collection):
    docs={}
    print(f"Processing {submodule}")
    for attribute_name in dir(submodule):
        if attribute_name.startswith('_'):
            continue
        
        attribute = getattr(submodule, attribute_name)
        full_name = f"{submodule.__name__}.{attribute_name}"

        # Check if attribute is a function, method, class, and not a _SpecialGenericAlias
        if not isinstance(attribute, _SpecialGenericAlias):
            if inspect.isfunction(attribute) or inspect.ismethod(attribute) or inspect.isclass(attribute):
                if inspect.isclass(attribute):
                    for method_name in dir(attribute):
                        if method_name.startswith('_'):
                            continue
                        try:
                            method = getattr(attribute, method_name)
                            if inspect.isfunction(method) or inspect.ismethod(method):
                                docstring,source_code=get_function_info(module, method, f"{full_name}.{method_name}")
                                docs[f"{full_name}.{method_name}"]={'attribute':attribute,'full_name':full_name,
                                                      'docstring':docstring,'source_code':source_code}
                            else:
                                docstring,source_code=get_class_info(module, attribute, full_name)
                                docs[full_name]={'attribute':attribute,'full_name':full_name,
                                                      'docstring':docstring,'source_code':source_code} 
                        except:
                            continue
                else:
                    try:
                        docstring,source_code=get_function_info(module, attribute, full_name)
                        docs[full_name]={'attribute':attribute,'full_name':full_name,
                                              'docstring':docstring,'source_code':source_code} #TODO: replace source code with function signature?
                    except:
                        continue
    if len(docs)>0:
        ids=collection.get()['ids']
        docs={doc:docs[doc] for doc in docs if doc not in ids}
        print(f'Length of new docs is len(docs)')
        docs = get_expanded_descriptions(docs)
        metadatas=[{"function_name": docs[doc]['full_name'], "docstring": docs[doc]['docstring'], "source_code": docs[doc]['source_code']} for doc in docs]
        documents=[docs[doc]['expanded_description'] for doc in docs]
        ids=[doc for doc in docs]
        # Add to ChromaDB collection
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

# def process_class_methods(module, cls, class_full_name):
#     for method_name in dir(cls):
#         if method_name.startswith('_'):
#             continue

#         method = getattr(cls, method_name)
#         if inspect.isfunction(method) or inspect.ismethod(method):
#             process_item(module, method, f"{class_full_name}.{method_name}")

def get_docstrings(module,collection):
    if hasattr(module, '__path__'):  # It's a package
        for importer, modname, ispkg in pkgutil.walk_packages(module.__path__, prefix=module.__name__ + "."):
            try:
                # Load the submodule
                print(f"#### Processing submodule {modname}")
                submodule = importlib.import_module(modname)
                process_submodule(module, submodule,collection)
            except Exception as e:
                print(f"{modname}: {e}")
                # Skip modules that can't be imported
                continue
    else:  # It's a single module
        process_submodule(module, module,collection)
    

def retry_decorator(retry_count=5, delay_seconds=10):
    """A decorator for retrying a function call with a specified delay and retry count."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retry_count):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"Attempt {attempt + 1} failed with error: {e}")
                    if attempt < retry_count - 1:
                        time.sleep(delay_seconds)
            raise Exception(f"All {retry_count} attempts failed")
        return wrapper
    return decorator

def check_and_trim_tokens(prompt, model):
    encoding = tiktoken.get_encoding("cl100k_base")
    max_length_dict = {
        'gpt-3.5-turbo-0125': 16385,
        'gpt-4-0125-preview':128000, #max tokens out is 4096
        "text-embedding-ada-002":8192,
    }
    max_tokens = max_length_dict[model]
    tokens=encoding.encode(prompt)
    if len(tokens) > max_tokens:
        print(f"Trimming prompt from {len(tokens)} characters to fit within token limit.")
        return encoding.decode(tokens[:max_tokens])
    return prompt
       
@retry_decorator(retry_count=3, delay_seconds=5)
def ask_gpt(prompt, model="gpt-3.5-turbo-0125",**kwargs):
    """Send a prompt to GPT and get a response."""
    checked_prompt = check_and_trim_tokens(prompt, model)
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": checked_prompt}
        ],
        **kwargs
    )
    return response.choices[0].message.content.strip()
        
def process_ask_gpt_in_parallel(prompts, prompt_names, max_workers=8, model="gpt-3.5-turbo-1106",**kwargs):
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ask_gpt, prompt, model,**kwargs): name for prompt, name in zip(prompts, prompt_names)}
        # Setting up tqdm progress bar
        with tqdm(total=len(prompts), desc="Processing Prompts") as progress:
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    results[name] = result
                except Exception as e:
                    print(f"Error processing prompt '{name}': {e}")
                progress.update(1)  # Update the progress for each completed task
    return results

def get_expanded_descriptions(docs,max_workers=8,model="gpt-3.5-turbo-1106"):
    prompt = "Explain the function '{func_name}' with its docstring '{docstring}' and source code:\n{source_code}\nIn simple terms:"
    
    prompts={doc: check_and_trim_tokens(prompt.format(func_name=docs[doc]['full_name'],
                              docstring=docs[doc]['docstring'],
                              source_code=docs[doc]['source_code']),model)
             for doc in docs}
    
    responses=process_ask_gpt_in_parallel(prompts.values(), prompts.keys(), model=model,max_workers=max_workers)
    for key in responses:
        docs[key]['expanded_description']=responses[key]
    return docs

def query_function(query,collection, n_results=5):
    # Query the ChromaDB collection
    result = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    cleaned_results = {}
    for i in range(len(result['ids'][0])):
        func = result['ids'][0][i]
        description = result['documents'][0][i]
        docstring = result['metadatas'][0][i]['docstring']
        cleaned_results[func] = {'description': description, 'docstring': docstring}

    return cleaned_results


# Example usage of embedding
def example_1():
    collection=start_chromadb()
    #submodule example (file)
    #this example gets stuff from the __init__.py that is imported by the script, .. not ideal..
    import mira.modeling.viz
    get_docstrings(mira.modeling.viz,collection)  # Process a library 
    res = query_function("template_model",collection)
    return res

def example_2():
    import mira.modeling
    collection=start_chromadb()
    get_docstrings(mira.modeling,collection)  # Process a library 
    res = query_function("petrinet",collection)
    return res

def full():
    import mira
    collection=start_chromadb()
    get_docstrings(mira,collection)  # Process a library 
    print(query_function("petrinet",collection))
    return collection
