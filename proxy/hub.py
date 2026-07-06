import asyncio

class Hub:
    def __init__(self):
        self.clients = set()

    def register(self) -> asyncio.Queue:
        """
        Register a new client and return a queue for receiving messages.
        """
        queue = asyncio.Queue()
        self.clients.add(queue)
        return queue
    
    def unregister(self, queue: asyncio.Queue):
        """
        Unregister a client and remove its queue.
        """
        self.clients.remove(queue)
        
    async def broadcast(self, message):
        """
        Broadcast a message to all registered clients.
        """
        for queue in self.clients:
            await queue.put(message)
            
    