import { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';

const API_URL = "https://gaming-backlog-api.onrender.com";

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

  useEffect(() => {
    fetchGames();
  }, []);

  console.log(getStatusCounts());

  return (
    <div>
      <h1>My Game Backlog</h1>

        <BarChart width={400} height={300} data={getStatusCounts()}>
          <XAxis dataKey="status" />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="count" fill="#8884d8" />
        </BarChart>

    {games.map((game) => (
      <p key={game.id}>
        {editingId === game.id ? (
          <>
            <input
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
            />
            <input
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value)}
            />
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
            {game.title} — {game.status}
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
          </>
        )}
      </p>
    ))}

    <div>
      <button onClick={() => fetchRecommendations("resume")}>
        What should I keep playing?
      </button>
      <button onClick={() => fetchRecommendations("something_new")}>
          Something new?
      </button>

       {recommendations.map((rec) => (
        <div key={rec.title}>
          <p><strong>{rec.title}</strong> — {rec.status} (score: {rec.score})</p>
          <p>{rec.reason}</p>
         </div>
        ))}
    </div>

      <form onSubmit={(e) => {
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
        <input
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          placeholder="Status"
        />
        <button type="submit">Add Game</button>
      </form>
    </div>
  );
}

export default App;