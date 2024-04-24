# Definitions


### resource
> A representation of a [document](#document) or other item that can be loaded into a vector store.  
> As many resources are too large or complex to be vectorized in to a single vector, the resource may be
[chunked](#chunk) in to multiple [records](#record) which will be vectorized and stored separately. Each record can be
mapped back to the resource if needed.  
> A resource may be an image or other binary file that requires a different [embedding function](#embedding-function)
than do other documents.  
> Each resource should be uniquely identifiable via a single URI.


### document
> A file whose contents is made up of words that can be split up at word or line boundaries and not lose meaning for
each [chunk](#chunk) generated.  
> Examples include [documentation](#documentation) (README.md, Website content (doc page on the web)), code files, text
files, etc.  


### chunk
> A subportion of a document or other resource for the purpose of ensuring generated embeddings are encoding the
appropriate amount of meaning for the chose embedding vector-size.  
> If a large document is embedded into a small vector, then semantic meaning will be lost since the vector must cover
the entire document. But if the document is chunked such that embeddings are generated for each paragraph, more semantic
meaning can be preserved.  
> Meanwhile, if chunks are too small, the embeddings lose information on the contextual whole, also resulting in poor
results.


### record
> This is what is actually stored in and retrieved from the vector store.  
>   
> A record may contain:
> - Content only: The record's content contains the full set of data used to generate the embeddings, stored in and
retrievable from the vector store. Used in case where transient information is embedded or data which does not have a
permanent resource or a URI cannot be generated.
> - URI only: The record does not contain the content. Instead the URI can be passed to a [loader](#loader) to retrieve
the full content. This will be the case for things such as images in which a single embedding is created for the image,
but content of the image file are not particularly useful in most sitatuations.
> - Content and URI: The content stored with the record is the data used to generate the record's embeddings, but a
resource is also available. The content may or may not match the full contents of resource identified by the URI. This
may represent a record generated from a record that was split up for embedding.


### partition
> A logical splitting of records within a vector store. All records must be in a partition. If no partition is provided,
the records will be placed in a partition named `default`.  
> Only a single partition can be searched or retrieved at a time.  
> It is expected that all records in a partition were all created using the same
[embdding function](#embedding-function). While this is not strictly enforced, symantic querying will be unpredicable if
records with different embedding functions are intermixed.


### corpus
> A corpus bundles any local vector store(s) and all local resources into a single package. The corpus should contain
everything needed to perform RAG lookups over the vectordb and retrieve the content requested.

### documentation
> Documents that explain how the code works, either conceptually or concretely.  
> May contain code examples, but should be human-readable, not a code file.


### prompt
> Text that is provided to an LLM agent that provides both a request and contextual information for the LLM to generate
an appropriate response to the provided request.


### example
> May refer to either a [code example](#code-example) or a [training example](#training-example).


### code example
> A section of sample code that demonstrates how to perform an action using code.


### training example
> Consists of a [prompt](#prompt) and a [code example](#code-example) and optionally an block of comments to explaining
the intention, etc.  
> These examples are embedded and then provided to the agent via RAG on a per-demand basis or are preemptively provided
to the agent to assist with code generation if the example is evaluated to likely to be helpful for code generation
based on the request.


### embedding function
> A function that takes a record and produces a vector of embedding values (floats) which is then stored in a vector
store to be queried over later.


### loader
> A class that finds sources to be embedded, and can retrieve the contents of a document based on a URI later on.
> Example sources include files on a filesystem, package libraries for a programming language, a github repository, a
documentation website, etc...


### store
> A vector database that is responsible for storing and querying over records.


### embedder
> A class that takes an instance of a loader, store, and optionally, an embedding function and applies rules to load the
appropriate resources from the loader in to the store with the correct embeddings.


## Additional details
* A resource is a file/entity that can be identified by a URI and loaded later, such as a file, webpage URL, github file
reference, etc.
* A document can be a type of resource.
* A resource may or may not be chunked during embedding.
* Each chunk is stored as a separate record in the db.
* A record may or may not contain the actual content of the chunk, depending on the embedding/ingestion rules.
* The embeddings on the record will be for the chunk, whether the content exists on the record or not.
* A record without content should have a URI set so the content can be fetched if needed.
* A record can have either:
  * Both content and a URI (With the URI usually pointing to the entire file that the content is a portion of)
  * Content but no URI
  * URI but no content
* During ingestion, a resource may generate records that go in to different partitions. E.g. A code file may generate
both "documentation" records and "code" records, or a PDF may generation "documentation" records and "image" records.
