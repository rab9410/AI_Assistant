from app.rag import RAG_ENGINE


class PlaybookRouter:

    def __init__(self):
        self.rules = {
            "coding": ["code", "python", "script", "function", "error", "debug"],
            "research": ["research", "study", "explain", "analysis", "information"],
            "system_design": ["architecture", "system", "design", "structure"],
            "writing": ["write", "email", "essay", "message", "summary"],
            "tools": ["weather", "price", "search", "market", "crypto"],
        }

    def classify(self, query: str):

        q = query.lower()

        matches = []

        for playbook, keywords in self.rules.items():
            if any(word in q for word in keywords):
                matches.append(playbook)

        return matches

    def retrieve_playbooks(self, query: str):

        categories = self.classify(query)

        context = RAG_ENGINE.get_knowledge(query)

        return {
            "categories": categories,
            "context": context
        }


ROUTER = PlaybookRouter()