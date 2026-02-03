"""
CLI Commands for Conversation History Management

Usage:
    python -m conversation list
    python -m conversation show <id>
    python -m conversation search <query>
    python -m conversation export <id>
    python -m conversation import <file>
"""
import sys
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from conversation.conversation_manager import ConversationManager
from conversation.json_handler import ConversationJSONHandler
from models.conversation import ConversationStatus


console = Console()

# Initialize managers
def get_manager():
    """Get conversation manager instance"""
    return ConversationManager()


def get_json_handler():
    """Get JSON handler instance"""
    return ConversationJSONHandler()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """LLM Smart Router - Conversation History CLI"""
    pass


# ==================== List Commands ====================

@cli.command()
@click.option('--user', '-u', help='Filter by user ID')
@click.option('--topic', '-t', help='Filter by topic ID')
@click.option('--status', '-s', type=click.Choice(['active', 'paused', 'closed', 'archived']), 
              help='Filter by status')
@click.option('--limit', '-l', default=20, help='Maximum number of results')
@click.option('--offset', default=0, help='Pagination offset')
@click.option('--sort', default='updated_at', 
              type=click.Choice(['created_at', 'updated_at', 'title', 'message_count']),
              help='Sort field')
@click.option('--ascending/--descending', default=False, help='Sort order')
@click.option('--json-output', '-j', is_flag=True, help='Output as JSON')
def list(user: Optional[str], topic: Optional[str], status: Optional[str],
         limit: int, offset: int, sort: str, ascending: bool, json_output: bool):
    """List conversations with filtering"""
    manager = get_manager()
    
    # Parse status
    status_filter = None
    if status:
        status_filter = ConversationStatus(status)
    
    conversations = manager.list_conversations(
        user_id=user,
        topic_id=topic,
        status=status_filter,
        sort_by=sort,
        ascending=ascending,
        limit=limit,
        offset=offset
    )
    
    if json_output:
        click.echo(json.dumps([c.to_dict() for c in conversations], indent=2, ensure_ascii=False))
        return
    
    if not conversations:
        console.print("[yellow]No conversations found.[/yellow]")
        return
    
    table = Table(title=f"Conversations ({len(conversations)} found)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Messages", justify="right")
    table.add_column("Updated", style="dim")
    
    for conv in conversations:
        status_style = {
            ConversationStatus.ACTIVE: "green",
            ConversationStatus.PAUSED: "yellow",
            ConversationStatus.CLOSED: "red",
            ConversationStatus.ARCHIVED: "dim"
        }.get(conv.status, "white")
        
        table.add_row(
            conv.id[:8] + "...",
            conv.title[:40] + "..." if len(conv.title) > 40 else conv.title,
            f"[{status_style}]{conv.status.value}[/{status_style}]",
            str(conv.message_count),
            conv.updated_at.strftime("%Y-%m-%d %H:%M")
        )
    
    console.print(table)


@cli.command()
def topics():
    """List all topics"""
    manager = get_manager()
    topics_list = manager.get_all_topics()
    
    if not topics_list:
        console.print("[yellow]No topics found.[/yellow]")
        return
    
    table = Table(title="Topics")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Description", style="dim")
    table.add_column("Created", style="dim")
    
    for topic in topics_list:
        table.add_row(
            topic.id[:8] + "...",
            topic.name,
            topic.description[:40] + "..." if topic.description and len(topic.description) > 40 else (topic.description or ""),
            topic.created_at.strftime("%Y-%m-%d")
        )
    
    console.print(table)


# ==================== Show Commands ====================

@cli.command()
@click.argument('conversation_id')
@click.option('--messages/--no-messages', default=True, help='Show messages')
@click.option('--limit', default=50, help='Maximum messages to show')
@click.option('--json-output', '-j', is_flag=True, help='Output as JSON')
def show(conversation_id: str, messages: bool, limit: int, json_output: bool):
    """Show conversation details"""
    manager = get_manager()
    
    conversation = manager.get_conversation(conversation_id)
    if not conversation:
        console.print(f"[red]Conversation not found: {conversation_id}[/red]")
        sys.exit(1)
    
    if json_output:
        data = conversation.to_dict()
        if messages:
            msgs = manager.get_messages(conversation_id, limit=limit)
            data['messages'] = [m.to_dict() for m in msgs]
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return
    
    # Show conversation info
    status_color = {
        ConversationStatus.ACTIVE: "green",
        ConversationStatus.PAUSED: "yellow",
        ConversationStatus.CLOSED: "red",
        ConversationStatus.ARCHIVED: "dim"
    }.get(conversation.status, "white")
    
    info = Panel(
        f"[bold]{conversation.title}[/bold]\n"
        f"ID: {conversation.id}\n"
        f"Status: [{status_color}]{conversation.status.value}[/{status_color}]\n"
        f"Messages: {conversation.message_count}\n"
        f"Created: {conversation.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Updated: {conversation.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Topic ID: {conversation.topic_id or 'None'}\n"
        f"User ID: {conversation.user_id or 'None'}",
        title="Conversation Details"
    )
    console.print(info)
    
    if messages and conversation.message_count > 0:
        msgs = manager.get_messages(conversation_id, limit=limit)
        
        console.print(f"\n[bold]Messages (showing {min(len(msgs), limit)} of {conversation.message_count}):[/bold]")
        
        for msg in msgs:
            role_color = {
                "user": "blue",
                "assistant": "green",
                "system": "dim"
            }.get(msg.role.value, "white")
            
            content_preview = msg.get_text()[:100] + "..." if len(msg.get_text()) > 100 else msg.get_text()
            
            console.print(f"\n[{role_color} bold]{msg.role.value.upper()}[/{role_color} bold] "
                         f"[dim]({msg.created_at.strftime('%H:%M:%S')})[/dim]")
            console.print(f"  {content_preview}")


# ==================== Create Commands ====================

@cli.command()
@click.option('--title', '-t', help='Conversation title')
@click.option('--user', '-u', help='User ID')
@click.option('--topic', help='Topic ID')
@click.option('--message', '-m', help='Initial message')
def create(title: Optional[str], user: Optional[str], topic: Optional[str], message: Optional[str]):
    """Create a new conversation"""
    manager = get_manager()
    
    conversation = manager.create_conversation(
        user_id=user or "",
        first_message=message,
        topic_id=topic
    )
    
    if title:
        manager.update_conversation(conversation.id, title=title)
        conversation = manager.get_conversation(conversation.id)
    
    console.print(f"[green]Created conversation:[/green] {conversation.id}")
    console.print(f"  Title: {conversation.title}")
    console.print(f"  Created: {conversation.created_at.strftime('%Y-%m-%d %H:%M:%S')}")


@cli.command()
@click.argument('name')
@click.option('--description', '-d', help='Topic description')
@click.option('--color', '-c', default='#3B82F6', help='Topic color')
def topic(name: str, description: Optional[str], color: str):
    """Create a new topic"""
    manager = get_manager()
    
    topic = manager.create_topic(
        name=name,
        description=description,
        color=color
    )
    
    console.print(f"[green]Created topic:[/green] {topic.id}")
    console.print(f"  Name: {topic.name}")
    console.print(f"  Color: {topic.color}")


# ==================== Update/Delete Commands ====================

@cli.command()
@click.argument('conversation_id')
@click.option('--title', '-t', help='New title')
@click.option('--status', '-s', type=click.Choice(['active', 'paused', 'closed', 'archived']), help='New status')
@click.option('--topic', help='New topic ID (use "none" to remove)')
def update(conversation_id: str, title: Optional[str], status: Optional[str], topic: Optional[str]):
    """Update a conversation"""
    manager = get_manager()
    
    conversation = manager.get_conversation(conversation_id)
    if not conversation:
        console.print(f"[red]Conversation not found: {conversation_id}[/red]")
        sys.exit(1)
    
    status_enum = None
    if status:
        status_enum = ConversationStatus(status)
    
    topic_id = topic
    if topic == "none":
        topic_id = None
    
    updated = manager.update_conversation(
        conversation_id=conversation_id,
        title=title,
        status=status_enum,
        topic_id=topic_id
    )
    
    console.print(f"[green]Updated conversation:[/green] {updated.id}")
    console.print(f"  Title: {updated.title}")
    console.print(f"  Status: {updated.status.value}")


@cli.command()
@click.argument('conversation_id')
@click.confirmation_option(prompt='Are you sure you want to delete this conversation?')
def delete(conversation_id: str):
    """Delete a conversation"""
    manager = get_manager()
    
    conversation = manager.get_conversation(conversation_id)
    if not conversation:
        console.print(f"[red]Conversation not found: {conversation_id}[/red]")
        sys.exit(1)
    
    success = manager.delete_conversation(conversation_id)
    if success:
        console.print(f"[green]Deleted conversation:[/green] {conversation_id}")
    else:
        console.print(f"[red]Failed to delete conversation[/red]")
        sys.exit(1)


# ==================== Message Commands ====================

@cli.command()
@click.argument('conversation_id')
@click.argument('role', type=click.Choice(['user', 'assistant', 'system']))
@click.argument('content')
@click.option('--model', help='Model name')
def message(conversation_id: str, role: str, content: str, model: Optional[str]):
    """Add a message to a conversation"""
    from models.message import MessageRole
    
    manager = get_manager()
    
    conversation = manager.get_conversation(conversation_id)
    if not conversation:
        console.print(f"[red]Conversation not found: {conversation_id}[/red]")
        sys.exit(1)
    
    message = manager.add_message(
        conversation_id=conversation_id,
        role=MessageRole(role),
        text=content,
        model=model
    )
    
    console.print(f"[green]Added message:[/green] {message.id}")
    console.print(f"  Role: {message.role.value}")
    console.print(f"  Content: {message.get_text()[:50]}...")


# ==================== Search Commands ====================

@cli.command()
@click.argument('query')
@click.option('--user', '-u', help='Filter by user ID')
@click.option('--limit', '-l', default=20, help='Maximum results')
@click.option('--json-output', '-j', is_flag=True, help='Output as JSON')
def search(query: str, user: Optional[str], limit: int, json_output: bool):
    """Search conversations"""
    manager = get_manager()
    
    conversations = manager.search_conversations(
        query=query,
        user_id=user,
        limit=limit
    )
    
    if json_output:
        click.echo(json.dumps([c.to_dict() for c in conversations], indent=2, ensure_ascii=False))
        return
    
    if not conversations:
        console.print(f"[yellow]No results for: {query}[/yellow]")
        return
    
    console.print(f"[green]Found {len(conversations)} results for: {query}[/green]\n")
    
    for conv in conversations:
        panel = Panel(
            f"[bold]{conv.title}[/bold]\n"
            f"ID: {conv.id}\n"
            f"Messages: {conv.message_count}\n"
            f"Updated: {conv.updated_at.strftime('%Y-%m-%d %H:%M')}",
            border_style="blue"
        )
        console.print(panel)


# ==================== Export/Import Commands ====================

@cli.command()
@click.argument('conversation_id', required=False)
@click.option('--output', '-o', help='Output file path')
@click.option('--all', 'export_all', is_flag=True, help='Export all conversations')
@click.option('--topic', help='Export conversations by topic')
def export(conversation_id: Optional[str], output: Optional[str], export_all: bool, topic: Optional[str]):
    """Export conversation(s) to JSON"""
    handler = get_json_handler()
    
    if not conversation_id and not export_all and not topic:
        console.print("[red]Error: Provide conversation_id, --all, or --topic[/red]")
        sys.exit(1)
    
    try:
        if output:
            output_path = Path(output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"export_{timestamp}.json")
        
        if conversation_id:
            # Single conversation
            conv_id_int = int(conversation_id)
            result_path = handler.export_to_file(output_path, conversation_ids=[conv_id_int])
        elif topic:
            # By topic
            topic_id_int = int(topic)
            result_path = handler.export_to_file(output_path, topic_id=topic_id_int)
        else:
            # All conversations
            result_path = handler.export_to_file(output_path)
        
        console.print(f"[green]Exported to:[/green] {result_path}")
        
    except ValueError as e:
        console.print(f"[red]Invalid ID format: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Export failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('filepath')
@click.option('--topic', '-t', help='Assign imported conversations to topic')
def import_file(filepath: str, topic: Optional[str]):
    """Import conversations from JSON file"""
    handler = get_json_handler()
    
    file_path = Path(filepath)
    if not file_path.exists():
        console.print(f"[red]File not found: {filepath}[/red]")
        sys.exit(1)
    
    try:
        topic_id_int = int(topic) if topic else None
        imported_ids = handler.import_from_file(file_path, topic_id_int)
        
        console.print(f"[green]Successfully imported {len(imported_ids)} conversation(s)[/green]")
        for cid in imported_ids:
            console.print(f"  - {cid}")
            
    except ValueError as e:
        console.print(f"[red]Invalid topic ID: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Import failed: {e}[/red]")
        sys.exit(1)


# ==================== Stats Command ====================

@cli.command()
@click.option('--user', '-u', help='Filter by user ID')
@click.option('--json-output', '-j', is_flag=True, help='Output as JSON')
def stats(user: Optional[str], json_output: bool):
    """Show conversation statistics"""
    manager = get_manager()
    
    stats_data = manager.get_stats(user_id=user)
    
    if json_output:
        click.echo(json.dumps(stats_data, indent=2))
        return
    
    table = Table(title="Conversation Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")
    
    table.add_row("Total Conversations", str(stats_data['total_conversations']))
    table.add_row("Active Conversations", str(stats_data['active_conversations']))
    table.add_row("Total Messages", str(stats_data['total_messages']))
    table.add_row("Today's Conversations", str(stats_data['today_conversations']))
    table.add_row("Avg Messages/Conversation", f"{stats_data['average_messages_per_conversation']:.1f}")
    
    console.print(table)


# ==================== Interactive Mode ====================

@cli.command()
def interactive():
    """Start interactive mode (REPL)"""
    console.print("[bold green]LLM Smart Router CLI - Interactive Mode[/bold green]")
    console.print("Type 'help' for commands, 'exit' to quit.\n")
    
    manager = get_manager()
    
    while True:
        try:
            command = console.input("[bold blue]>>>[/bold blue] ").strip()
            
            if command in ['exit', 'quit']:
                break
            
            if command == 'help':
                console.print("\n[bold]Available commands:[/bold]")
                console.print("  list           - List conversations")
                console.print("  show <id>      - Show conversation details")
                console.print("  create         - Create new conversation")
                console.print("  search <query> - Search conversations")
                console.print("  stats          - Show statistics")
                console.print("  topics         - List topics")
                console.print("  help           - Show this help")
                console.print("  exit/quit      - Exit\n")
                continue
            
            if command.startswith('list'):
                # Parse list command
                parts = command.split()
                limit = 20
                for i, part in enumerate(parts):
                    if part == '--limit' and i + 1 < len(parts):
                        limit = int(parts[i + 1])
                
                conversations = manager.list_conversations(limit=limit)
                for conv in conversations:
                    console.print(f"  {conv.id[:8]}... | {conv.title[:40]} | {conv.message_count} msgs")
            
            elif command.startswith('show '):
                conv_id = command[5:].strip()
                conversation = manager.get_conversation(conv_id)
                if conversation:
                    console.print(f"\n[bold]{conversation.title}[/bold]")
                    console.print(f"  ID: {conversation.id}")
                    console.print(f"  Status: {conversation.status.value}")
                    console.print(f"  Messages: {conversation.message_count}")
                    console.print(f"  Updated: {conversation.updated_at}\n")
                else:
                    console.print(f"[red]Conversation not found: {conv_id}[/red]")
            
            elif command.startswith('search '):
                query = command[7:].strip()
                results = manager.search_conversations(query)
                console.print(f"\n[green]Found {len(results)} results:[/green]")
                for conv in results:
                    console.print(f"  - {conv.title}")
            
            elif command == 'topics':
                topics = manager.get_all_topics()
                for topic in topics:
                    console.print(f"  {topic.id[:8]}... | {topic.name}")
            
            elif command == 'stats':
                s = manager.get_stats()
                console.print(f"\nConversations: {s['total_conversations']}")
                console.print(f"Messages: {s['total_messages']}")
                console.print(f"Active: {s['active_conversations']}\n")
            
            else:
                console.print("[yellow]Unknown command. Type 'help' for available commands.[/yellow]")
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Use 'exit' to quit.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    
    console.print("\n[green]Goodbye![/green]")


if __name__ == "__main__":
    cli()
