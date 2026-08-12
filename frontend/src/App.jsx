import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';
import './App.css';

const API_URL = "https://gaming-backlog-api.onrender.com";

const STATUS_OPTIONS = ["Not Started", "Playing", "Paused", "Finished", "Dropped"];

// Session length options for both the Add Game form and the quiz.
// `value` is what gets sent to the backend/stored in the DB, `label` is
// what the user actually sees.
const SESSION_OPTIONS = [
  { value: "quick", label: "Quick (under 30 min)" },
  { value: "medium", label: "Medium (30–90 min)" },
  { value: "long", label: "Long (90+ min)" },
];

function App() {
  const [games, setGames] = useState([]);
  const [title, setTitle] = useState('');
  const [status, setStatus] = useState('');
  const [sessionLength, setSessionLength] = useState('');

  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editStatus, setEditStatus] = useState('');
  const [recommendations, setRecommendations] = useState([]);

  // Autocomplete state for the "Game title" field in the Add Game form
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  // Prevents the search effect from firing again right after the user
  // clicks a suggestion (which also changes `title`)
  const skipNextSearch = useRef(false);

  // --- Quiz state ---
  // quizStep tracks where we are in the conversation:
  // 'closed' -> not open at all
  // 'time'   -> asking "how much time do you have?"
  // 'genre'  -> asking "what are you in the mood for?"
  // 'result' -> showing the recommendation
  const [quizStep, setQuizStep] = useState('closed');
  const [quizTime, setQuizTime] = useState(null);
  const [availableGenres, setAvailableGenres] = useState([]);
  const [quizResult, setQuizResult] = useState(null);
  const [quizLoading, setQuizLoading] = useState(false);

  const fetchGames = () => {
    axios.get(`${API_URL}/games`).then((response) => {
      setGames(response.data);
    })
  }

  const fetchRecommendations = (mode) => {                      
    axios.get(`${API_URL}/recommendations?mode=${mode}`).then((response) => {
      setRecommendations(response.data);
    });
  };

  const getStatusCounts = () => {
    const counts = {};
    games.forEach((game) => {
      counts[game.status] = (counts[game.status] || 0) + 1;
    });
    return Object.entries(counts).map(([status, count]) => ({status,count}));
  };

  const getStatusClass = (status) => {
    return "status-" + status.toLowerCase().replace(/\s+/g, "-");
  };

  useEffect(() => {
    fetchGames();
  }, []);

  // Debounced search-as-you-type: waits 300ms after the user stops typing
  // before hitting the backend, so we're not firing a request per keystroke.
  useEffect(() => {
    if (skipNextSearch.current) {
      skipNextSearch.current = false;
      return;
    }
    const timeoutId = setTimeout(() => {
      if (title.trim().length < 2) {
        setSuggestions([]);
        return;
      }
      axios.get(`${API_URL}/games/search`, { params: { q: title } })
        .then((response) => {
          setSuggestions(response.data);
          setShowSuggestions(true);
        })
        .catch(() => setSuggestions([]));
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [title]);

  const selectSuggestion = (name) => {
    skipNextSearch.current = true;
    setTitle(name);
    setSuggestions([]);
    setShowSuggestions(false);
  };

  // --- Quiz functions ---

  // Starts the quiz: reset any previous answer, fetch which genres actually
  // exist in the backlog (so we never offer a genre with zero games), then
  // move to the first question.
  const startQuiz = () => {
    setQuizResult(null);
    setQuizTime(null);
    axios.get(`${API_URL}/genres`).then((response) => {
      setAvailableGenres(response.data);
      setQuizStep('time');
    });
  };

  // User tapped a time option -> remember it, move to the genre question.
  const answerTime = (value) => {
    setQuizTime(value);
    setQuizStep('genre');
  };

  // User tapped a genre (or "Anything") -> call the backend, show the result.
  const answerGenre = (genreValue) => {
    setQuizLoading(true);
    axios.get(`${API_URL}/quiz-recommendation`, {
      params: { session_length: quizTime, genre: genreValue },
    }).then((response) => {
      setQuizResult(response.data);
      setQuizStep('result');
      setQuizLoading(false);
    }).catch(() => {
      setQuizLoading(false);
    });
  };

  const closeQuiz = () => {
    setQuizStep('closed');
  };

  console.log(getStatusCounts());

  return (
    <div>
      <h1>My Game Backlog</h1>

      <div className="chart-panel">
        <BarChart width={400} height={300} data={getStatusCounts()}>
          <XAxis dataKey="status" />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="count" fill="#5ee6a0" />
        </BarChart>
      </div>

      <div className="game-list">
        {games.map((game) => (
          <div key={game.id} className={`game-card ${getStatusClass(game.status)}`}>
            {editingId === game.id ? (
              <>
                <input
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                />
                <select
                  value={editStatus}
                  onChange={(e) => setEditStatus(e.target.value)}
                >
                  {STATUS_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
                <button onClick={() => {
                  axios.patch(`${API_URL}/games/${game.id}`, null, {
                    params: { title: editTitle, status: editStatus }
                  }).then(() => {
                    setEditingId(null);
                    fetchGames();
                  });
                }}>
                  Save
                </button>
              </>
            ) : (
              <>
                <div className="game-info">
                  {game.cover_url && (
                    <img
                      src={game.cover_url}
                      alt={`${game.title} cover`}
                      className="game-cover"
                    />
                  )}
                  <div>
                    <div className="game-title">{game.title}</div>
                    <div className="game-status">{game.status}</div>
                  </div>
                </div>
                <div className="game-actions">
                  <button onClick={() => {
                    setEditingId(game.id);
                    setEditTitle(game.title);
                    setEditStatus(game.status);
                  }}>
                    Edit
                  </button>
                  <button onClick={() => {
                    axios.delete(`${API_URL}/games/${game.id}`).then(() => {
                      fetchGames();
                    });
                  }}>
                    Delete
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>

      {/* --- "What should I play?" quiz --- */}
      <div className="quiz-panel">
        {quizStep === 'closed' && (
          <button className="quiz-start-button" onClick={startQuiz}>
            🎮 Help me pick something to play
          </button>
        )}

        {quizStep !== 'closed' && (
          <div className="quiz-chat">
            {/* Assistant's first question is always shown once we're past 'closed' */}
            <div className="quiz-bubble quiz-bubble-assistant">
              How much time do you have?
            </div>

            {/* Once the user has answered the time question, show it as
                their own chat bubble, then move on to whichever comes next */}
            {quizTime && (
              <div className="quiz-bubble quiz-bubble-user">
                {SESSION_OPTIONS.find((o) => o.value === quizTime)?.label}
              </div>
            )}

            {quizStep === 'time' && (
              <div className="quiz-options">
                {SESSION_OPTIONS.map((option) => (
                  <button key={option.value} onClick={() => answerTime(option.value)}>
                    {option.label}
                  </button>
                ))}
              </div>
            )}

            {(quizStep === 'genre' || quizStep === 'result') && (
              <div className="quiz-bubble quiz-bubble-assistant">
                What are you in the mood for?
              </div>
            )}

            {quizResult && (
              <div className="quiz-bubble quiz-bubble-user">
                {quizResult.genre_choice || 'Anything'}
              </div>
            )}

            {quizStep === 'genre' && (
              <div className="quiz-options">
                {availableGenres.map((g) => (
                  <button key={g} onClick={() => answerGenre(g)}>{g}</button>
                ))}
                <button onClick={() => answerGenre('any')}>Anything</button>
              </div>
            )}

            {quizLoading && (
              <div className="quiz-bubble quiz-bubble-assistant">Thinking…</div>
            )}

            {quizStep === 'result' && quizResult && (
              <div className="quiz-bubble quiz-bubble-assistant quiz-result">
                {quizResult.found ? (
                  <>
                    {quizResult.cover_url && (
                      <img
                        src={quizResult.cover_url}
                        alt={`${quizResult.title} cover`}
                        className="quiz-result-cover"
                      />
                    )}
                    <div>
                      <div className="quiz-result-title">{quizResult.title}</div>
                      <div className="quiz-result-reason">{quizResult.reason}</div>
                    </div>
                  </>
                ) : (
                  <div>{quizResult.message}</div>
                )}
              </div>
            )}

            {quizStep === 'result' && (
              <button className="quiz-restart-button" onClick={startQuiz}>
                Ask again
              </button>
            )}

            <button className="quiz-close-button" onClick={closeQuiz}>
              Close
            </button>
          </div>
        )}
      </div>

      <div className="rec-panel">
        <div className="rec-buttons">
          <button onClick={() => fetchRecommendations("resume")}>
            What should I keep playing?
          </button>
          <button onClick={() => fetchRecommendations("something_new")}>
            Something new?
          </button>
        </div>

        {recommendations.map((rec) => (
          <div key={rec.title} className="rec-card">
            <span className="rec-score">{rec.score}</span>
            <div className="rec-title">{rec.title} — {rec.status}</div>
            <div className="rec-reason">{rec.reason}</div>
          </div>
        ))}
      </div>

      <form className="add-form" onSubmit={(e) => {
        e.preventDefault();
        axios.post(`${API_URL}/games`, null, {
          params: { title: title, status: status, session_length: sessionLength || null }
        }).then(() => {
          setTitle('');
          setStatus('');
          setSessionLength('');
          setSuggestions([]);
          fetchGames();
        });
      }}>
        <div className="autocomplete-wrapper">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder="Game title"
            autoComplete="off"
          />
          {showSuggestions && suggestions.length > 0 && (
            <ul className="autocomplete-list">
              {suggestions.map((s) => (
                <li
                  key={s.name}
                  className="autocomplete-item"
                  onMouseDown={() => selectSuggestion(s.name)}
                >
                  {s.cover_url && (
                    <img src={s.cover_url} alt="" className="autocomplete-cover" />
                  )}
                  <div>
                    <div className="autocomplete-name">{s.name}</div>
                    {s.genres.length > 0 && (
                      <div className="autocomplete-genre">{s.genres.join(', ')}</div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="" disabled>Status</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
        <select
          value={sessionLength}
          onChange={(e) => setSessionLength(e.target.value)}
        >
          <option value="">Session length (optional)</option>
          {SESSION_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        <button type="submit">Add Game</button>
      </form>
    </div>
  );
}

export default App;