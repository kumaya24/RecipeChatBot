from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

store = {}

def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

class RecipeAssistant:
    def __init__(self, raw_recipe_text: str):
        self.llm         = OllamaLLM(model="llama3.1")
        self.recipe_text = raw_recipe_text

        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a helpful chef assistant. "
             "Answer questions based on the recipe below.\n\n"
             "{recipe_content}\n\n"
             "If the user's message selected this recipe AND asked a question "
             "(e.g. 'I'll take the first one, what are its ingredients?'), "
             "skip any acknowledgement and just answer the question directly."),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ])

        self.chain = self.prompt.partial(recipe_content=self.recipe_text) | self.llm
        self.brain = RunnableWithMessageHistory(
            self.chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )

    def ask(self, user_question: str, session_id: str) -> str:
        return self.brain.invoke(
            {"input": user_question},
            config={"configurable": {"session_id": session_id}},
        )


if __name__ == "__main__":
    bot = RecipeAssistant("Recipe of bananapie: 2 Eggs, Flour. Step 1: Mix.")
    print(f"Bot: {bot.ask('What are the ingredients?', 'session_1')}")
    print(f"Bot: {bot.ask('Can i put banana in it?', 'session_1')}")
    print(f"Bot: {bot.ask('What I am making tho?', 'session_1')}")