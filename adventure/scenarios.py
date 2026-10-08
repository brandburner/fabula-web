"""Scenario registry: one interface the views speak, two kinds behind it.

'dracula' is the hand-authored prototype (engine/scenario/author/parser).
Every other slug is a projected world read from the narrative graph
(projection/explore/narrator), configured in settings.ADVENTURE_WORLDS.
"""
from django.conf import settings
from django.http import Http404

from . import author, engine, explore, narrator, parser, projection, store
from .scenario import REVISION as DRACULA_REVISION


class DraculaScenario:
    slug = 'dracula'
    session_key = 'adventure_run'          # unchanged: existing saves keep working
    revision = DRACULA_REVISION
    viewpoint = 'Jonathan Harker'
    meta = {
        'kicker': 'FABULA LABS <span>/</span> PLAYABLE WORLDS · 001', 'title': 'Enter the story.',
        'intro': 'Every place holds a memory.<br>Every memory has a connection.',
        'brief': 'You are Jonathan Harker. The Count knew a thought you had never shared. Sister Agatha is waiting for your account.',
        'goal': 'Find out how he knew.', 'address': 'fabula://play/dracula/s01e01',
        'underbar': 'DRACULA / 01 <span class="underbar-dot">·</span> THE THINGS WE CARRY',
        'caption': 'A small, authored investigation seeded from Fabula’s narrative graph. Explore in your own words. Your story is saved in this browser’s session.',
        'workshop': 'Some details are unfinished. Examine the window or Agatha’s bag here; the fireplace or dresser in the castle. The bag contains a manuscript, stake and hammer. Read the manuscript to write a passage you can revisit. Each accepted passage becomes a permanent part of this playthrough.',
        'slot_label': 'details written', 'restart_confirm': 'Start the investigation again? Your written object descriptions will be kept.',
        'filename': 'fabula-dracula-written-world.html', 'page_title': 'Enter the story — fabula.',
        'description': 'A playable story-world experiment. Enter Dracula, follow a memory, and discover what connects it all.',
    }

    def new_state(self):
        return engine.new_state()

    def available(self, state):
        return engine.available(state)

    def resolve(self, command, state):
        action = engine.resolve(command, state)
        return ('action', action) if action else ('unknown', None)

    def candidates(self, clean, state):
        return parser.candidates(clean, engine.available(state))

    def refusal(self, state, status, payload, clean):
        return [engine.block(parser.refusal(clean), 'system'),
                engine.block('Try ' + ', '.join(engine.suggestions(state)) + '.', 'hint')]

    def gap(self, state, action):
        return engine.gap(state, action)

    def write(self, slot, state, backend, run=None):
        return author.write_object(slot, selected_backend=backend)

    def budget_exceeded(self, state, calls):
        return state['model_calls'] + calls >= 12              # per save, as before

    def transition(self, state, action, authored=None):
        return engine.transition(state, action, authored)

    def suggestions(self, state):
        return engine.suggestions(state)

    def public_state(self, state, version, run_id, backend):
        result = engine.public_state(state, version, run_id, backend)
        result['viewpoint'] = self.viewpoint
        return result

    def compile_world(self, state):
        return engine.compile_world(state)

    def restart(self, state):
        fresh = engine.new_state()
        fresh.update({k: state[k] for k in ('objects', 'authored', 'model_calls', 'frozen')})
        fresh['parser_aliases'] = state.get('parser_aliases', {})
        return fresh


class ProjectionScenario:
    viewpoint = explore.VIEWPOINT

    def __init__(self, config):
        self.config = config
        self.slug = config['slug']
        self.session_key = f'adventure_run:{self.slug}'
        self.revision = f"{self.slug}:{projection.REVISION}"
        self._world = None

    @property
    def world(self):
        if self._world is None:
            self._world = projection.load_world(self.config)
            if self._world is None:
                raise Http404('This world’s episode is not published here.')
            explore.ensure_index(self._world)
        return self._world

    @property
    def meta(self):
        world = self.world
        ep, rep = world['episode'], world['report']
        code = f"S{ep['season']:02d}E{ep['number']:02d}"
        return {
            'kicker': 'FABULA LABS <span>/</span> PROJECTED WORLDS · ' + self.config.get('number', '002'),
            'title': self.config.get('title', 'Walk the record.'),
            'intro': self.config.get('intro', f"{rep['rooms']} places. {rep['events']} moments.<br>Nothing written by hand."),
            'brief': self.config.get('brief', f"You are an unseen witness inside {world['series']['title']} {code}. "
                                              'Every place, person and object here is read from the narrative graph; '
                                              'each passage is written from the record the first time you ask for it.'),
            'goal': self.config.get('goal', 'See how far the record can carry you.'),
            'address': f"fabula://play/{self.slug}/{code.lower()}",
            'underbar': f"{world['series']['title'].upper()} / {ep['number']:02d} <span class=\"underbar-dot\">·</span> {ep['title'].upper()}",
            'caption': 'An experiment: the episode’s locations, events, people and objects projected straight from Fabula’s graph into a walkable world. Your position is saved in this browser’s session.',
            'workshop': f"This world writes itself as people explore it. Every passage is unwritten until someone asks: "
                        f"{rep['passage_slots']} are possible across {rep['events']} moments. The first accepted passage "
                        'becomes part of the world for every visitor after. The local author renders the source record '
                        'verbatim; the LLM author paraphrases it. If the record changes, its passages are written afresh.',
            'slot_label': 'passages in this world', 'calls_label': 'written by the LLM author', 'restart_confirm': 'Return to the first moment? Written passages will be kept.',
            'filename': f'fabula-{self.slug}-written-world.html', 'page_title': f"{world['series']['title']} {code} — fabula.",
            'description': f"Walk {world['series']['title']} {code} as a text adventure projected from Fabula’s narrative graph.",
        }

    def new_state(self):
        return explore.new_state(self.world)

    def available(self, state):
        return explore.available(self.world, state)

    def resolve(self, command, state):
        return explore.parse(self.world, state, command)

    def candidates(self, clean, state):
        return explore.candidates(self.world, state, clean)

    def refusal(self, state, status, payload, clean):
        return explore.refusal(self.world, state, status, payload)

    @staticmethod
    def mode(state):
        return state.get('author_backend', author.backend())

    def gap(self, state, action):
        """A key to write only if the world lacks a passage in this visitor's
        backend. Frozen visitors never write; they read whatever exists."""
        key = explore.needs_passage(self.world, state, action)
        if not key or state['frozen']:
            return None
        return None if store.lookup(self.slug, self.world, key, self.mode(state), exact=True) else key

    def write(self, key, state, backend, run=None):
        """Auto-accept: the written passage joins the world for every visitor."""
        return store.save(self.slug, self.world, key, narrator.write(self.world, key, backend), run)

    def budget_exceeded(self, state, calls):
        return not store.llm_budget_left(self.slug)            # per world, all visitors

    def transition(self, state, action, written=None):
        key = explore.needs_passage(self.world, state, action)
        passage = written or (store.lookup(self.slug, self.world, key, self.mode(state)) if key else None)
        return explore.transition(self.world, state, action, passage, fresh=written is not None)

    def suggestions(self, state):
        return explore.suggestions(self.world, state)

    def public_state(self, state, version, run_id, backend):
        return explore.public_state(self.world, state, version, run_id, backend, store.stats(self.slug, self.world))

    def compile_world(self, state):
        """The offline edition is the shared world as written so far."""
        return explore.compile_world(self.world, state, store.passages_for(self.slug, self.world, self.mode(state)),
                                     store.stats(self.slug, self.world))

    def restart(self, state):
        return explore.restart(self.world, state)


def get(slug):
    if slug == 'dracula':
        return DraculaScenario()
    for config in getattr(settings, 'ADVENTURE_WORLDS', []):
        if config['slug'] == slug:
            return ProjectionScenario(config)
    raise Http404('No such world.')
