import { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';
import './App.css';

const API_URL = "https://gaming-backlog-api.onrender.com";

const STATUS_OPTIONS = ["Not Started", "Playing", "Paused", "Finished", "Dropped"];

function App() {
  const [games, setGames] = useState([]);
  const [title, setTitle] = useState('');
  const [status, setStatus] = useState('');

  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editStatus, setEditStatus] = useState('');
  const [recommendations, setRecommendations] = useState([]);

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
          params: { title: title, status: status }
        }).then(() => {
          setTitle('');
          setStatus('');
          fetchGames();
        });
      }}>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Game title"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="" disabled>Status</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
        <button type="submit">Add Game</button>
      </form>
    </div>
  );
}

export default App;