import asyncio
import json
from typing import TypedDict, Annotated, Sequence
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END
from tools import search_knowledge_base, get_current_weather, set_rag_step_queue, get_last_rag_context, reset_tool_call_guards
from conversation_storage import ConversationStorage
from utils import get_env

# 初始化模型
API_KEY = get_env("ARK_API_KEY")
MODEL = get_env("MODEL")
BASE_URL = get_env("BASE_URL")

# Agent 状态定义
class AgentState(TypedDict):
    """
    Agent 状态容器
    面试考点：LangGraph 的状态管理
    """
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]

# 初始化工具列表
tools = [get_current_weather, search_knowledge_base]
tool_map = {tool.name: tool for tool in tools}

def create_agent_instance():
    """
    创建基于 LangGraph 的 ReAct Agent
    技术原理：手动实现 ReAct 循环（Thought -> Action -> Observation）
    面试考点：为什么用 LangGraph 而不是 prebuilt？
    答：更灵活的控制，可自定义节点和边，便于调试和扩展
    """
    model = init_chat_model(
        model=MODEL,
        model_provider="openai",
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.3,
        stream_usage=True,
    )
    
    # 绑定工具到模型
    model_with_tools = model.bind_tools(tools)
    
    def call_model(state: AgentState):
        """调用 LLM 进行推理"""
        messages = state['messages']
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}
    
    def should_continue(state: AgentState) -> str:
        """判断是否需要调用工具"""
        last_message = state['messages'][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "call_tool"
        return "end"
    
    def call_tool(state: AgentState):
        """执行工具调用"""
        last_message = state['messages'][-1]
        tool_call = last_message.tool_calls[0]
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        
        if tool_name in tool_map:
            try:
                result = tool_map[tool_name].invoke(tool_args)
                # 添加观察结果到消息历史
                observation = AIMessage(content=str(result))
                return {"messages": [observation]}
            except Exception as e:
                error_msg = f"工具调用失败：{str(e)}"
                return {"messages": [AIMessage(content=error_msg)]}
        return {"messages": []}
    
    # 构建状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("agent", call_model)
    workflow.add_node("action", call_tool)
    
    # 设置入口点
    workflow.set_entry_point("agent")
    
    # 添加条件边
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "call_tool": "action",
            "end": END
        }
    )
    
    # 从 action 回到 agent（形成循环）
    workflow.add_edge("action", "agent")
    
    # 编译图
    app = workflow.compile()
    
    return app, model

agent, model = create_agent_instance()
storage = ConversationStorage()

def summarize_old_messages(messages: list) -> str:
    """将旧消息总结为摘要"""
    old_conversation = "\n".join([
        f"{'用户' if msg.type == 'human' else 'AI'}: {msg.content}"
        for msg in messages
    ])
    summary_prompt = f"请总结以下对话的关键信息：\n{old_conversation}\n总结："
    summary = model.invoke(summary_prompt).content
    return summary

async def chat_with_agent_stream(user_text: str, user_id: str = "default_user", session_id: str = "default_session"):
    """
    流式对话函数
    技术原理：使用 LangGraph 的 stream 方法获取生成器
    面试考点：异步生成器与 SSE 推送
    """
    # 加载历史消息
    messages = storage.load_messages(session_id, limit=50)
    # 转换为 LangChain 消息对象
    lc_messages = []
    for msg in messages:
        if msg['role'] == 'user':
            lc_messages.append(HumanMessage(content=msg['content']))
        else:
            lc_messages.append(AIMessage(content=msg['content']))
    # 如果历史过长，摘要
    if len(lc_messages) > 50:
        summary = summarize_old_messages(lc_messages[:40])
        lc_messages = [SystemMessage(content=f"之前的对话摘要：\n{summary}")] + lc_messages[40:]

    lc_messages.append(HumanMessage(content=user_text))

    # 清理残留
    get_last_rag_context(clear=True)
    reset_tool_call_guards()

    output_queue = asyncio.Queue()
    set_rag_step_queue(output_queue)

    full_response = ""

    async def agent_worker():
        nonlocal full_response
        try:
            # 使用 LangGraph 的 stream 方法
            config = {"recursion_limit": 10}
            async for event in agent.astream(
                {"messages": lc_messages},
                config=config,
                stream_mode="values"  # 流式返回状态值
            ):
                # event 是完整的消息列表
                last_message = event['messages'][-1]
                content = last_message.content if isinstance(last_message.content, str) else ""
                if content:
                    full_response += content
                    await output_queue.put({"type": "content", "content": content})
        except Exception as e:
            await output_queue.put({"type": "error", "content": str(e)})
        finally:
            await output_queue.put(None)

    agent_task = asyncio.create_task(agent_worker())

    try:
        while True:
            event = await output_queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"
    except GeneratorExit:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
        raise
    finally:
        set_rag_step_queue(None)
        if not agent_task.done():
            agent_task.cancel()

    # 保存会话
    storage.save_message(session_id, "user", user_text)
    storage.save_message(session_id, "assistant", full_response, extra={"rag_trace": get_last_rag_context(clear=True)})
    yield "data: [DONE]\n\n"