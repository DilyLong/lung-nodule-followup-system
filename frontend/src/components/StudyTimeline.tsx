import type { Measurement, Study } from '../lib/api';

interface Props {
  studies: Study[];
}

export default function StudyTimeline({ studies }: Props) {
  return (
    <div className="timeline">
      {studies.map((study, index) => {
        const measurement: Measurement | undefined = study.measurements[0];
        return (
          <div className="timeline-item" key={study.id}>
            <div className="timeline-index">T{index + 1}</div>
            <div>
              <strong>{study.study_date}</strong>
              <p>{study.series_description}</p>
              {measurement && (
                <span>
                  最大径 {measurement.diameter_mm.toFixed(1)} mm · 平均 CT {measurement.mean_hu.toFixed(0)} HU · 实性 {measurement.solid_component_percent.toFixed(0)}%
                  {measurement.roi_area_mm2 != null && ` · ROI ${measurement.roi_area_mm2.toFixed(1)} mm²`}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
