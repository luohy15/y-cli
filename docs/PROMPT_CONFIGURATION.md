# Prompt Configuration for Y-CLI

This document explains how to configure and use prompts in Y-CLI.

> **Note:** This document refers to command line usage patterns. All commands use `y-cli` as the base command.

## Overview

Y-CLI provides a prompt management system that allows you to create, list, and delete prompt configurations. Prompts can be used to customize the behavior of your bots and interactions.

## Key Features

- Create custom prompts with descriptive names
- Manage multiple prompts for different use cases
- Associate prompts with specific bots
- Pre-configured MCP prompt for Model Context Protocol interactions

## Command Reference

### List Available Prompts

```bash
y-cli prompt list
```

Options:
- `--verbose` or `-v`: Show additional details including storage location

### Add a New Prompt

```bash
y-cli prompt add
```

Interactive prompts will ask for:
- Prompt name (unique identifier)
- Prompt content (the actual text of the prompt)
- Description (optional)

### Delete a Prompt

```bash
y-cli prompt delete <name>
```

Where `<name>` is the name of the prompt you want to delete.

## Using Prompts with Bots

When configuring bots, you can associate one or more prompts with a bot:

```bash
y-cli bot add
```

During bot configuration, you'll be asked to select prompts to use with this bot. You can select multiple prompts which will be combined in the order specified.

Alternatively, you can manually edit your bot configuration file to set prompts:

```jsonl
# In your Y-CLI bot_config.jsonl file
{
  "name": "my-bot",
  "provider": "openai",
  "api_key": "your-api-key",
  "model": "gpt-4",
  "prompts": ["technical", "friendly"],
  "mcp_servers": []
}
```

## Default Prompts

Y-CLI comes with a pre-configured MCP prompt that provides instructions for using Model Context Protocol tools and resources. This prompt is automatically available with the name "mcp".

## Storage Location

Prompt configurations are stored in a JSONL file at:

- On macOS: `~/Library/Preferences/y-cli/prompt_config.jsonl`
- On Linux: `~/.config/y-cli/prompt_config.jsonl`

You can edit this file directly with a text editor if you prefer manual configuration over using the CLI commands.

## Example Prompt Configuration

Here's an example of creating a technical writing prompt:

```bash
y-cli prompt add
```

Then enter:
- Name: technical
- Content: "You are a technical writing assistant. Respond concisely and clearly. Use active voice and include specific examples when appropriate."
- Description: Technical writing style prompt

## Best Practices

1. **Use descriptive names**: Choose prompt names that clearly indicate their purpose
2. **Keep prompts focused**: Create separate prompts for different aspects (technical style, domain knowledge, etc.)
3. **Combine when needed**: Associate multiple prompts with a bot to compose behavior
4. **Version your prompts**: Consider adding version information in prompt names for important changes
5. **Test prompts thoroughly**: Verify that prompts produce the expected behavior in different contexts

## Troubleshooting

- If a prompt isn't being applied, verify it exists with `y-cli prompt list`
- Check that the prompt name is correctly specified in your bot configuration
- The "default" and "mcp" prompts cannot be deleted

## Advanced Usage

### Viewing System Message Logs

When using Cloudflare AI Gateway, you can view the system message logs to debug and understand how your prompts are being processed. Currently, system messages are not saved by default because they can be large.

If you need to save or print system messages for debugging purposes, please contact the project author for assistance.
