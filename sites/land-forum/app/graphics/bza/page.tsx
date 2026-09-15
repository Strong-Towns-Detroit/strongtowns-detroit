import Link from 'next/link';
import BzaGraphicStudio from '../../../components/BzaGraphicStudio';
import './studio.css';

export const metadata = { title: 'Create a BZA graphic | Land Forum', description: 'Explore recorded Detroit BZA cases and create a sourced chart or count card.' };
export default function BzaGraphicsPage() {
  return <main id="main" className="studio-page"><header className="site-header"><Link className="wordmark" href="/">LAND FORUM</Link><nav><Link href="/atlas/">BZA Atlas</Link><Link href="/methods/">Methods & sources</Link></nav></header><section className="studio-intro"><p className="kicker">DETROIT BOARD OF ZONING APPEALS</p><h1>Create a graphic from the public record.</h1><p>Choose cases, check what the numbers mean, and make a graphic to share. No account or installation needed.</p></section><BzaGraphicStudio /></main>;
}
