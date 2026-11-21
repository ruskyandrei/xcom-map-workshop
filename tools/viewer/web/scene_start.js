// The scene's page as it opens (app.js's startScene): the parts of it that are no one area's own. Here: the page's title
// and the patch preview's chip (showSceneTitle), View options' Full or Interior and the Map menu's items as the scene
// allows them (showSceneMenus), the import notes (showImportNotes) and the gizmo's Linked button as the export allows it
// (showLinked). The areas start their own parts of the scene in their modules; startScene calls each in the order the
// page always started them. Plain exports, each given what it needs of app.js; nothing here runs as the page loads.
import { plural, short, text } from './dom_words.js';
import { builderMode, data, loadErrorCount } from './editor_state.js';

// The page's title, and the chip of a patch preview.
export function showSceneTitle($) {
  document.title = `${data.name} · XCOM Map Workshop`;
  $('previewChip').hidden = !data.preview;
}
// View options' Full or Interior, and the Map menu's own items (shown for a whole map's original layout).
export function showSceneMenus($, projectsAvailable) {
  $('scenery').value=data.preview ? 'full' : data.tactical?.recommendedView || 'full';
  $('sceneryGroup').hidden=!data.playableBounds || data.scope!=='map';
  $('projectSize').hidden = !projectsAvailable();     // Map grid: any whole map
  $('projectClear').hidden = !projectsAvailable();
  $('projectMissions').hidden = !projectsAvailable();
  $('projectPicture').hidden = !projectsAvailable();
}
// The import notes: their count on the header's button and their list.
export function showImportNotes($) {
  // Import notes: a count on the header button; the list opens from it. Preview notes count as warnings.
  const issues = data.preview ? [...data.preview.notes,...data.diagnostics.filter(d => !data.preview.notes.some(n => n.source === d.source && n.message === d.message))] : data.diagnostics;
  $('issueCount').textContent = issues.length + loadErrorCount || '';
  $('issueCount').classList.toggle('warn', Boolean(data.preview?.notes.length || loadErrorCount));
  for (const issue of issues) {
    const item = text($('diagnostics'), 'div', '', 'note');
    text(item, 'strong', short(issue.source)); text(item, 'div', issue.message);
  }
  if (loadErrorCount) text($('diagnostics'), 'div', `${plural(loadErrorCount, 'piece')} could not be displayed; the browser console has the errors.`, 'note');
}
// The gizmo's Linked button: off, with why, for an export without links.
export function showLinked($) {
  // Exports before version 12 carry no prefab/partner links: say so instead of silently moving one actor.
  const hasLinks = builderMode || data.objects.some(o => 'prefab' in o);
  $('editLinked').disabled = !hasLinks;
  if (!hasLinks) {
    $('editLinked').classList.remove('on');
    $('editLinked').title = 'Linked pieces need a re-export: this export has no prefab/partner links. Re-export the map (export version 12) and restart the viewer server.';
  }
}
