import Link from "next/link";
import { api } from "@/lib/api";

export const revalidate = 3600;

export default async function HorsesPage({
  searchParams,
}: {
  searchParams: Promise<{ search?: string }>;
}) {
  const { search = "" } = await searchParams;
  const data = await api<{ horses: { id: number; name: string }[] }>(
    `/api/horses?limit=200${search ? `&search=${encodeURIComponent(search)}` : ""}`
  );
  const horses = data?.horses ?? [];

  return (
    <>
      <h1>Horses</h1>
      <p className="subtitle">Profiles, form and distance/going specialisation.</p>

      <form className="form-row" action="/horses" method="get">
        <div>
          <label htmlFor="search">Search</label>
          <input id="search" name="search" defaultValue={search} placeholder="horse name" />
        </div>
        <button type="submit">Search</button>
      </form>

      {horses.length === 0 ? (
        <div className="empty">No horses found.</div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Name</th>
              </tr>
            </thead>
            <tbody>
              {horses.map((h) => (
                <tr key={h.id}>
                  <td>
                    <Link href={`/horses/${h.id}`}>{h.name}</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
