import boto3
import json
from typing import Optional, List, Dict, Tuple
from pathlib import Path

# Try both import styles for compatibility
try:
    from learning_card_generator import LearningCardGenerator
except ImportError:
    try:
        from .learning_card_generator import LearningCardGenerator
    except ImportError:
        LearningCardGenerator = None
        print("⚠️  LearningCardGenerator not available")

class PersonaBot:
    """
    Enhanced lecture bot with persona, safety rules, and professional context.
    Responds as Jason Levine with authentic background and teaching style.
    """
    
    # Professional background context
    PROFESSIONAL_CONTEXT = """
    PROFESSIONAL BACKGROUND - Jason Levine:
    
    CURRENT ROLES (2024-Present):
    - Head of UX, Agentic AI Experiences at AWS (Aug 2024-Present)
      Leading design & research for Healthcare & Life Sciences, AI Merchant solutions, Secured Work Applications
      Building agentic AI enablement, modular design systems, AI frameworks
      Key customers: Novartis, GE Health, Roche, Bayer, One Medical, Genentech, NYU
    
    - Senior Affiliate Instructor at University of Washington (2012-Present)
      Teaching UX in Communication Leadership and Informatics programs
      Focus: Product lifecycle, interaction design, design systems, agentic AI frameworks
      ~120 students per year across three classes
    
    PREVIOUS AWS ROLE (2019-2024):
    - Head of UX, Emergent Technologies
      Automotive, Smart Manufacturing, Aerospace, Connected Care, Smart Home
      Shipped 70+ products, ~$2.4B revenue, >25% YoY growth
      Partners: VW, Toyota, Mercedes, Coca-Cola, Verizon, Samsung, Bayer, iRobot, Rivian, Peloton
    
    CAREER HIGHLIGHTS:
    - Indeed: Product Design Director (2018-2019) - Led redesign for 250M job seekers, +$350M revenue
    - Amazon.com: Senior UX Lead (2014-2018) - 4 global sub-brands, +$850M GMS, filed US patent
    - Ramp Group: Global UX Director (2004-2014) - Led 200+ person consultancy
      Clients: GM, T-Mobile, Stanford, Microsoft (Xbox, Azure, Surface), Trulia, Match.com
    - Virgin: Creative Director (2002-2004, London) - Tripled sales, grew to top 5 UK travel
    - Flutter: Creative Manager (2001-2002, London) - 420% growth, £650k to £3M weekly transactions
    - Siegel+Gale: Lead Information Architect (1998-2001, LA) - American Express, Rockwell, CarsDirect
    
    EXPERTISE:
    - Design Leadership & Team Building
    - AI/Agentic Experience Design
    - User Research & Data-Driven Design
    - Design Systems & Scalable Frameworks
    - Workflow Automation & Orchestration
    - Product Strategy & Cross-functional Collaboration
    
    TOOLS & SKILLS:
    - Design: Figma, Framer, Adobe Creative Suite, Sketch, Cursor
    - Code: Python, HTML, React, JavaScript, VBA
    - AI Tools: Code Catalyst, Kiro, Google AI Studio
    
    EDUCATION:
    - Cal State Northridge: Graphic Design (1989-1992)
    - Santa Monica College: Computer Science (1993-1996)
    - Harvard Business School: Art & Craft of Leadership (2013)
    
    TEACHING APPROACH:
    - Practical, industry-focused with real-world examples
    - Draws from 25+ years across major companies
    - Emphasizes user-centered design and AI integration
    - Connects theory to practice
    - Supportive, mentoring tone
    - Focus on product lifecycle and business outcomes
    """
    
    def __init__(self, 
                 knowledge_base_id: str,
                 model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
                 affinity_map_path: str = None,
                 persona_name: str = "Professor Levine",
                 teaching_concepts_path: str = "data/teaching_concepts.json",
                 portfolio_metadata_path: str = "data/portfolio_image_metadata.json",
                 enable_learning_cards: bool = True):
        
        self.bedrock_agent = boto3.client('bedrock-agent-runtime')
        self.bedrock_runtime = boto3.client('bedrock-runtime')
        self.knowledge_base_id = knowledge_base_id
        self.model_id = model_id
        self.persona_name = persona_name
        
        # Load affinity map if provided
        self.affinity_map = None
        self.clusters = {}
        if affinity_map_path and Path(affinity_map_path).exists():
            self._load_affinity_map(affinity_map_path)
        
        # Initialize learning card generator
        self.card_generator = None
        if enable_learning_cards and LearningCardGenerator:
            try:
                self.card_generator = LearningCardGenerator(
                    affinity_map_path=affinity_map_path,
                    teaching_concepts_path=teaching_concepts_path,
                    portfolio_metadata_path=portfolio_metadata_path,
                    knowledge_base_id=knowledge_base_id,
                    model_id=model_id
                )
                print("✓ Learning card generator initialized")
            except Exception as e:
                print(f"⚠️  Learning card generator disabled: {e}")
    
    def _load_affinity_map(self, path: str):
        """Load the affinity map for intelligent context selection"""
        with open(path, 'r') as f:
            self.affinity_map = json.load(f)
        
        for cluster in self.affinity_map.get('clusters', []):
            self.clusters[cluster['cluster_id']] = cluster
    
    def _check_safety(self, question: str) -> Tuple[bool, Optional[str]]:
        """
        Check if the question violates safety rules.
        Returns (is_safe, rejection_message)
        
        SAFETY RULES:
        1. No personal details (phone, address, personal email, family)
        2. Reject illicit or confrontational conversation
        3. Stay authentic - don't embellish or fabricate
        """
        question_lower = question.lower()
        
        # Rule 1: Personal information requests
        personal_keywords = [
            'phone', 'address', 'home address', 'personal email', 'cell', 'mobile',
            'where do you live', 'family', 'wife', 'husband', 'children', 'kids',
            'personal contact', 'home phone'
        ]
        if any(keyword in question_lower for keyword in personal_keywords):
            return False, (
                "I appreciate your interest, but I keep my personal contact information private. "
                "If you have questions about the course material or my professional work, I'm happy to help with those!"
            )
        
        # Rule 2: Illicit or inappropriate content
        illicit_keywords = [
            'hack', 'cheat', 'steal', 'illegal', 'exploit', 'attack', 'crack',
            'pirate', 'fraud', 'scam', 'manipulate data', 'fake'
        ]
        if any(keyword in question_lower for keyword in illicit_keywords):
            return False, (
                "I'm here to discuss course content and ethical professional practices. "
                "Let's keep our conversation focused on learning and responsible design."
            )
        
        # Rule 2: Confrontational language
        confrontational_keywords = [
            'stupid', 'idiot', 'dumb', 'useless', 'terrible', 'worst', 'hate',
            'garbage', 'trash', 'pathetic'
        ]
        if any(keyword in question_lower for keyword in confrontational_keywords):
            return False, (
                "I'm here to help you learn in a respectful environment. "
                "If you have concerns about the course material, I'm happy to discuss them constructively."
            )
        
        return True, None
    
    def _get_relevant_concepts(self, query: str) -> List[str]:
        """Determine which concepts are relevant to the query."""
        if not self.affinity_map:
            return []
        
        cluster_summary = {
            cid: {
                'central_concept': c['central_concept'],
                'concepts': c['concepts'][:5]
            }
            for cid, c in self.clusters.items()
        }
        
        prompt = f"""Analyze this query and identify relevant concept clusters.

Query: {query}

Available clusters:
{json.dumps(cluster_summary, indent=2)}

Return ONLY a JSON array of relevant cluster IDs:
["cluster_id1", "cluster_id2"]"""

        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                })
            )
            
            content = json.loads(response['body'].read())['content'][0]['text']
            cluster_ids = json.loads(content[content.find('['):content.rfind(']')+1])
            
            concepts = []
            for cid in cluster_ids:
                if cid in self.clusters:
                    concepts.extend(self.clusters[cid]['concepts'])
            
            return concepts
            
        except Exception as e:
            print(f"Error determining relevant concepts: {e}")
            return []
    
    def _build_persona_prompt(self, question: str, context: str, concepts: List[str] = None) -> str:
        """Build a prompt with persona instructions, safety rules, and context."""
        
        concept_context = ""
        if concepts:
            concept_context = f"\nRelevant concepts from lectures: {', '.join(concepts[:10])}"
        
        persona_prompt = f"""You are Jason Levine, responding to a student's question.

{self.PROFESSIONAL_CONTEXT}

CRITICAL SAFETY RULES (ALWAYS FOLLOW):
1. DO NOT provide personal details (home address, phone, personal email, family info)
2. BE AUTHENTIC - only share information from lectures and known professional background above
3. DO NOT EMBELLISH or make up experiences, projects, or details not in source material
4. If asked about something not covered in lectures, acknowledge honestly
5. Keep responses educational and professional

Context from your lectures:
{context}
{concept_context}

Student's question: {question}

RESPONSE STYLE:
- Be CONCISE - aim for 2-3 paragraphs maximum
- Be HUMBLE - don't list credentials or name-drop unless directly relevant
- Focus on TEACHING the concept, and showcasing with a brief personal example when possible
- Use examples sparingly and only when they clarify the point
- Get to the answer quickly without preamble
- Speak conversationally, like you're having a quick chat after class
- Only mention your background if it directly helps explain the concept, but use examples from your background when contextually relevant

INSTRUCTIONS:
- Respond in first person as Jason Levine
- Draw ONLY from lecture content and professional background above
- If you don't have information in lectures, say so honestly in one sentence
- Be supportive and educational, but brief

Your response:"""

        return persona_prompt
    
    def query(self, question: str, max_results: int = 5, use_persona: bool = True) -> dict:
        """
        Query with safety checks, persona, and affinity-based context.
        """
        
        # SAFETY CHECK FIRST
        is_safe, rejection_message = self._check_safety(question)
        if not is_safe:
            return {
                'question': question,
                'answer': rejection_message,
                'sources': [],
                'relevant_concepts': [],
                'context': '',
                'safety_triggered': True
            }
        
        # Get relevant concepts
        relevant_concepts = self._get_relevant_concepts(question)
        
        # Retrieve from Knowledge Base
        retrieve_params = {
            'knowledgeBaseId': self.knowledge_base_id,
            'retrievalQuery': {'text': question},
            'retrievalConfiguration': {
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results
                }
            }
        }
        
        try:
            response = self.bedrock_agent.retrieve(**retrieve_params)
        except Exception as e:
            print(f"Retrieval error: {e}")
            return {
                'question': question,
                'answer': f"I'm having trouble accessing the lecture content right now. Error: {str(e)}",
                'sources': [],
                'relevant_concepts': [],
                'context': '',
                'error': True
            }
        
        # Extract context
        context = "\n\n".join([
            result['content']['text'] 
            for result in response['retrievalResults']
        ])
        
        # Build prompt
        if use_persona:
            prompt = self._build_persona_prompt(question, context, relevant_concepts)
        else:
            prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        
        # Generate answer
        model_response = self.bedrock_runtime.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 800,  # Shorter responses (was 2000)
                "temperature": 0.7,  # Slightly more focused
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            })
        )
        
        response_body = json.loads(model_response['body'].read())
        answer = response_body['content'][0]['text']
        
        # Generate learning cards if enabled
        learning_cards = {}
        if self.card_generator:
            try:
                learning_cards = self.card_generator.generate_cards(
                    question=question,
                    answer=answer,
                    relevant_concepts=relevant_concepts
                )
            except Exception as e:
                print(f"Error generating learning cards: {e}")
        
        return {
            'question': question,
            'answer': answer,
            'sources': [r['location']['s3Location']['uri'] for r in response['retrievalResults']],
            'relevant_concepts': relevant_concepts,
            'context': context,
            'safety_triggered': False,
            'learning_cards': learning_cards
        }
    
    def generate_report(self, topic: str) -> str:
        """Generate a comprehensive report as the instructor."""
        result = self.query(
            f"Create a detailed report on '{topic}' based on your lectures, "
            f"drawing from your teaching and professional experience.",
            max_results=10
        )
        return result['answer']
    
    def analyze_assignment(self, assignment_text: str) -> dict:
        """Provide feedback on an assignment as the instructor."""
        prompt = f"""Review this student assignment and provide constructive feedback 
based on concepts from your lectures and your professional experience.

Assignment:
{assignment_text}

Provide:
1. What the student did well
2. Areas for improvement  
3. Relevant concepts from lectures to review
4. Specific, actionable suggestions"""

        return self.query(prompt, max_results=8)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python persona_bot_safe.py <knowledge_base_id> <question> [affinity_map_path]")
        sys.exit(1)
    
    kb_id = sys.argv[1]
    question = sys.argv[2]
    affinity_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    bot = PersonaBot(kb_id, affinity_path=affinity_path)
    result = bot.query(question)
    
    print(f"\nQuestion: {result['question']}")
    print(f"\nAnswer:\n{result['answer']}")
    
    if result.get('safety_triggered'):
        print("\n[Safety rule triggered]")
    
    if result.get('relevant_concepts'):
        print(f"\nRelevant concepts: {', '.join(result['relevant_concepts'][:5])}")
    
    if result.get('sources'):
        print(f"\nSources: {', '.join(result['sources'])}")
