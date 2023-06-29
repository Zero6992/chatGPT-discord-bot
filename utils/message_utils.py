from discord import Message

async def send_split_message(self, response: str, message: Message):
    char_limit = 1900
    if len(response) > char_limit:
        is_code_block = False
        parts = response.split("```")

        for i in range(len(parts)):
            if is_code_block:
                code_block_chunks = [parts[i][j:j+char_limit] for j in range(0, len(parts[i]), char_limit)]
                for chunk in code_block_chunks:
                    if self.is_replying_all:
                        await message.channel.send(f"```{chunk}```")
                    else:
                        await message.followup.send(f"```{chunk}```")
                is_code_block = False
            else:
                non_code_chunks = [parts[i][j:j+char_limit] for j in range(0, len(parts[i]), char_limit)]
                for chunk in non_code_chunks:
                    if self.is_replying_all:
                        await message.channel.send(chunk)
                    else:
                        await message.followup.send(chunk)
                is_code_block = True
    else:
        if self.is_replying_all:
            await message.channel.send(response)
        else:
            await message.followup.send(response)
