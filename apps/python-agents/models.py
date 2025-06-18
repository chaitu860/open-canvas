from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any, Literal # Moved Literal import here
from enum import Enum

# Enum Definitions from packages/shared/src/types.ts

class ArtifactLengthOptions(str, Enum):
    SHORTEST = "shortest"
    SHORT = "short"
    LONG = "long"
    LONGEST = "longest"

class ArtifactType(str, Enum): # Retained as it's used in ArtifactContent
    CODE = "code"
    TEXT = "text"

class LanguageOptions(str, Enum):
    ENGLISH = "english"
    MANDARIN = "mandarin"
    SPANISH = "spanish"
    FRENCH = "french"
    HINDI = "hindi"

class ProgrammingLanguageOptions(str, Enum):
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    CPP = "cpp"
    JAVA = "java"
    PHP = "php"
    PYTHON = "python"
    HTML = "html"
    SQL = "sql"
    JSON = "json"
    RUST = "rust"
    XML = "xml"
    CLOJURE = "clojure"
    CSHARP = "csharp"
    OTHER = "other"

class ReadingLevelOptions(str, Enum):
    PIRATE = "pirate"
    CHILD = "child"
    TEENAGER = "teenager"
    COLLEGE = "college"
    PHD = "phd"

# Interface Translations from packages/shared/src/types.ts

class CustomModelConfig(BaseModel):
    provider: str
    temperatureRange: Dict[str, float] # min, max, default, current
    maxTokens: Dict[str, int] # min, max, default, current
    azureConfig: Optional[Dict[str, str]] = None # azureOpenAIApiKey, azureOpenAIApiInstanceName, etc.

class ModelConfigurationParams(BaseModel):
    name: str
    label: str
    modelName: Optional[str] = None
    config: CustomModelConfig
    isNew: bool

class ArtifactContent(BaseModel): # Older version, might not be directly used by ArtifactV3 but good to have
    index: int
    content: str
    title: str
    type: ArtifactType # Uses the ArtifactType Enum
    language: str # Assuming this was meant to be a generic string, not LanguageOptions

class Artifact(BaseModel): # Older version
    id: str
    contents: List[ArtifactContent]
    currentContentIndex: int

# Corrected Definitions for V3 Artifacts
class ArtifactMarkdownV3(BaseModel):
    index: int
    type: Literal["text"] = "text"
    title: str
    fullMarkdown: str = Field(..., alias="fullMarkdown")

class ArtifactCodeV3(BaseModel):
    index: int
    type: Literal["code"] = "code"
    title: str
    language: ProgrammingLanguageOptions
    code: str

class ArtifactV3(BaseModel): # Uses corrected ArtifactMarkdownV3 and ArtifactCodeV3
    currentIndex: int
    contents: List[Union[ArtifactMarkdownV3, ArtifactCodeV3]]

class CodeHighlight(BaseModel):
    startCharIndex: int
    endCharIndex: int

class TextHighlight(BaseModel):
    fullMarkdown: str = Field(..., alias="fullMarkdown")
    markdownBlock: str = Field(..., alias="markdownBlock")
    selectedText: str = Field(..., alias="selectedText")

class CustomQuickAction(BaseModel):
    id: str
    title: str
    prompt: str
    includeReflections: bool
    includePrefix: bool
    includeRecentHistory: bool

class Reflections(BaseModel):
    styleRules: List[str]
    content: List[str]

class ContextDocument(BaseModel):
    name: str
    type: str # Could be an Enum if types are predefined
    data: str # Base64 encoded or plain text
    metadata: Optional[Dict[str, Any]] = None

class ExaMetadata(BaseModel): # For SearchResult
    id: str
    url: str
    title: str
    author: str
    publishedDate: str
    image: Optional[str] = None
    favicon: Optional[str] = None

class SearchResult(BaseModel): # Represents DocumentInterface<ExaMetadata>
    page_content: str
    metadata: ExaMetadata

# GraphInput from packages/shared/src/types.ts
# This will be a primary input model for FastAPI
# Uses the corrected ArtifactV3
class GraphInput(BaseModel):
    messages: Optional[List[Dict[str, Any]]] = None
    highlightedCode: Optional[CodeHighlight] = None
    highlightedText: Optional[TextHighlight] = None
    artifact: Optional[ArtifactV3] = None # Corrected
    next_node: Optional[str] = Field(None, alias="next")
    language: Optional[LanguageOptions] = None
    artifactLength: Optional[ArtifactLengthOptions] = None
    regenerateWithEmojis: Optional[bool] = None
    readingLevel: Optional[ReadingLevelOptions] = None
    addComments: Optional[bool] = None
    addLogs: Optional[bool] = None
    portLanguage: Optional[ProgrammingLanguageOptions] = None
    fixBugs: Optional[bool] = None
    customQuickActionId: Optional[str] = None
    webSearchEnabled: Optional[bool] = None
    webSearchResults: Optional[List[SearchResult]] = None


# OpenCanvasGraphAnnotation.State from apps/agents/src/open-canvas/state.ts
# This will be the internal state representation.
# Uses the corrected ArtifactV3
class OpenCanvasGraphState(BaseModel):
    messages: List[Dict[str, Any]]
    _messages: List[Dict[str, Any]] = Field(default_factory=list)

    highlightedCode: Optional[CodeHighlight] = None
    highlightedText: Optional[TextHighlight] = None
    artifact: Optional[ArtifactV3] = None # Corrected
    next_node: Optional[str] = Field(None, alias="next")
    language: Optional[LanguageOptions] = None
    artifactLength: Optional[ArtifactLengthOptions] = None
    regenerateWithEmojis: Optional[bool] = None
    readingLevel: Optional[ReadingLevelOptions] = None
    addComments: Optional[bool] = None
    addLogs: Optional[bool] = None
    portLanguage: Optional[ProgrammingLanguageOptions] = None
    fixBugs: Optional[bool] = None
    customQuickActionId: Optional[str] = None
    webSearchEnabled: Optional[bool] = None
    webSearchResults: Optional[List[SearchResult]] = None

# Placeholder for Langchain BaseMessage (commented out as in original, not used by current models)
# class BaseMessage(BaseModel):
#     content: Union[str, List[Any]]
#     role: Optional[str] = None
#     name: Optional[str] = None
#     type: str
#     additional_kwargs: Optional[Dict[str, Any]] = None
