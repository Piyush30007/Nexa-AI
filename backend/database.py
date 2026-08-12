import uuid
from datetime import datetime, timezone

from sqlalchemy import (create_engine,Column,String,Integer,Float, DateTime, ForeignKey, Text, JSON)
from sqlalchemy.orm import (sessionmaker,declarative_base,relationship)

from config import settings

#database conenction 
engine = create_engine( # this engine is uses for creating the connection between our python code and the database 
    settings.database_url,
    connect_args={
        "check_same_thread": False #allows the SQLite connection to be used across threads.
    } if settings.database_url.startswith("sqlite") else {}, #here it takes url of database that we have been settup in config file 
    #Only apply this SQLite-specific option when we're actually using SQLite
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)

#document 
#this column represesnt the docuument that we uploaded how it looks like in database 

class Document(Base):

    __tablename__ = "documents"

    id = Column(String,  primary_key=True, default=_uuid )

    filename = Column( String, nullable=False  )

    file_type = Column(   String , nullable=False )

    status = Column(  String,  default="processing" )

    num_chunks = Column(   Integer, default=0 )

    error_message = Column( Text, nullable=True )

    uploaded_at = Column(  DateTime,  default=_now )
    
    
    chunks = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )

#chunks
class Chunk(Base):

    __tablename__ = "chunks"

    id = Column(String,primary_key=True,default=_uuid,) #3every chunk gets a unique id 

    document_id = Column(String,ForeignKey("documents.id"),nullable=False )#which document this chunks beliongs to , and foreign key becuase document id must refers to existing document 

    # ID used to connect SQLite data with FAISS
    faiss_id = Column(Integer,  unique=True,  nullable=False, index=True,) #FAISS searches vectors, but your SQLite database stores the actual chunk information. So we need a bridge.
#above unique = true becuase two chunks cannot have same faiss id 
    chunk_index = Column( Integer, nullable=False, ) #This tells us the order of the chunk inside the document.

    text = Column(   Text, nullable=False,  )#actual text that is exctracted from pdf 

    page = Column(  Integer, nullable=True,  ) # this gives the page number from where chunk came from      

    document = relationship(
        "Document",
        back_populates="chunks",
    ) #gives source information 


#conversation : means how it will looks or store in database 

class Conversation(Base):

    __tablename__ = "conversations"

    id = Column( String,  primary_key=True,default=_uuid) #default = uuid asigin the unique random values to id which is important for the fronteend 

    title = Column( String,default="New conversation",)

    created_at = Column( DateTime, default=_now )

    messages = relationship( #links a conversation model to mesage model it tells the python the one conversation have many relation it is one to many relation
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


#messages 

class Message(Base):

    __tablename__ = "messages"

    id = Column( String,primary_key=True,default=_uuid)
    conversation_id = Column(String,ForeignKey("conversations.id"), nullable=False,)

    role = Column( String, nullable=False,)

    content = Column(Text,nullable=False,)

    # Example:
    # [
    #   {
    #       "document": "policy.pdf",
    #       "page": 11,
    #       "chunk_id": "...",
    #       "score": 0.56
    #   }
    # ]
    sources = Column(JSON,default=list, )

    created_at = Column(DateTime,default=_now,)

    conversation = relationship( #goes inside our message class and back propagate and find the convesation from it 
        "Conversation",
        back_populates="messages",
    )


#usage log 

class UsageLog(Base):

    __tablename__ = "usage_logs"

    id = Column(String,primary_key=True,default=_uuid,
    )

    request_id = Column(String,default=_uuid,)

    endpoint = Column(String,nullable=False,)

    model = Column(String,nullable=False,)

    input_tokens = Column(Integer,default=0,)

    output_tokens = Column(Integer,default=0,)

    latency_ms = Column(Float,default=0.0, )

    estimated_cost = Column(Float,default=0.0,  )

    was_grounded = Column(Integer,default=1, )

    timestamp = Column(DateTime,default=_now, )


#evaluation run 

class EvaluationRun(Base):

    __tablename__ = "evaluation_runs"

    id = Column(String,      primary_key=True,default=_uuid,  )

    timestamp = Column(     DateTime,     default=_now,  )

    num_cases = Column(  Integer,  default=0, )

    retrieval_accuracy = Column(   Float,  default=0.0, )

    answer_correctness = Column( Float, default=0.0,)

    citation_accuracy = Column(  Float,   default=0.0, )

    hallucination_rate = Column(Float,default=0.0, )

    avg_latency_ms = Column(Float,default=0.0, )

    results = Column(JSON,default=list,  )


#fast api database dependencies 
def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


#create database tables 

def init_db():

    Base.metadata.create_all(
        bind=engine
    )



