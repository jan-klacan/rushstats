//! Sample moments, type-7 quantiles and pairwise complete correlations.
use serde_json::{Value, json};

pub fn finite(x: f64) -> Option<f64> {
    x.is_finite().then_some(x)
}
fn sum(xs: impl Iterator<Item = f64>) -> f64 {
    let (mut total, mut correction) = (0., 0.);
    for x in xs {
        let y = x - correction;
        let t = total + y;
        correction = (t - total) - y;
        total = t;
    }
    total
}
/// Hyndman–Fan type 7, matching NumPy's linear and R's default quantiles.
pub fn quantile(sorted: &[f64], p: f64) -> Option<f64> {
    if sorted.is_empty() || !(0. ..=1.).contains(&p) {
        return None;
    }
    let index = (sorted.len() - 1) as f64 * p;
    let lo = index.floor() as usize;
    let hi = index.ceil() as usize;
    let w = index - lo as f64;
    let a = sorted[lo];
    let b = sorted[hi];
    // Preserve accuracy for nearby values, avoid overflow for opposite signs.
    Some(if (b - a).is_finite() {
        a + (b - a) * w
    } else {
        a * (1. - w) + b * w
    })
}

pub struct Numeric {
    pub sorted: Vec<f64>,
    pub mean: Option<f64>,
    pub variance: Option<f64>,
    pub std: Option<f64>,
    pub skewness: Option<f64>,
    pub kurtosis: Option<f64>,
}
impl Numeric {
    pub fn new(values: &[Option<f64>]) -> Self {
        let mut sorted: Vec<f64> = values.iter().flatten().copied().collect();
        sorted.sort_by(f64::total_cmp);
        let n = sorted.len() as f64;
        let mut result = Self {
            sorted,
            mean: None,
            variance: None,
            std: None,
            skewness: None,
            kurtosis: None,
        };
        if n == 0. {
            return result;
        }
        let anchor = quantile(&result.sorted, 0.5).unwrap_or(0.);
        let scale = result
            .sorted
            .iter()
            .map(|x| x.abs())
            .fold(0., f64::max)
            .max(f64::MIN_POSITIVE);
        let shifted: Vec<f64> = result
            .sorted
            .iter()
            .map(|&x| {
                if (x - anchor).is_finite() {
                    (x - anchor) / scale
                } else {
                    x / scale - anchor / scale
                }
            })
            .collect();
        let center = sum(shifted.iter().copied()) / n;
        result.mean = finite(anchor + center * scale);
        // Re-scale centered residuals to avoid moment underflow at tiny spreads.
        let residual_scale = shifted
            .iter()
            .map(|x| (x - center).abs())
            .fold(0., f64::max);
        if n > 1. && residual_scale == 0. {
            result.variance = Some(0.);
            result.std = Some(0.);
        }
        if residual_scale == 0. {
            return result;
        }
        let residuals: Vec<f64> = shifted
            .iter()
            .map(|x| (x - center) / residual_scale)
            .collect();
        let m2 = sum(residuals.iter().map(|x| x * x)) / n;
        if n > 1. {
            let std = (m2 * n / (n - 1.)).sqrt() * residual_scale * scale;
            result.std = finite(std);
            result.variance = finite(std * std);
        }
        if n > 2. {
            let m3 = sum(residuals.iter().map(|x| x.powi(3))) / n;
            result.skewness = finite((n * (n - 1.)).sqrt() / (n - 2.) * m3 / m2.powf(1.5));
        }
        if n > 3. {
            let m4 = sum(residuals.iter().map(|x| x.powi(4))) / n;
            let g2 = m4 / (m2 * m2) - 3.;
            result.kurtosis = finite((n - 1.) / ((n - 2.) * (n - 3.)) * ((n + 1.) * g2 + 6.));
        }
        result
    }
    pub fn unique(&self) -> usize {
        self.sorted
            .iter()
            .enumerate()
            .filter(|(i, x)| *i == 0 || **x != self.sorted[*i - 1])
            .count()
    }
    pub fn describe(&self, missing: usize, percentiles: &[f64]) -> Value {
        let q1 = quantile(&self.sorted, 0.25);
        let q3 = quantile(&self.sorted, 0.75);
        json!({"count":self.sorted.len(),"missing":missing,"mean":self.mean,"std":self.std,"variance":self.variance,
            "min":self.sorted.first(),"max":self.sorted.last(),
            "range":self.sorted.first().zip(self.sorted.last()).and_then(|(a,b)|finite(b-a)),
            "q1":q1,"median":quantile(&self.sorted,0.5),"q3":q3,"iqr":q1.zip(q3).and_then(|(a,b)|finite(b-a)),
            "percentiles":percentiles.iter().map(|p|json!({"percentile":p,"value":quantile(&self.sorted,p/100.)})).collect::<Vec<_>>()})
    }
    pub fn distribution(&self) -> Value {
        json!({"count":self.sorted.len(),"unique":self.unique(),"zeros":self.sorted.iter().filter(|&&v|v==0.).count(),"skewness":self.skewness,"excess_kurtosis":self.kurtosis,
            "q1":quantile(&self.sorted,0.25),"median":quantile(&self.sorted,0.5),"q3":quantile(&self.sorted,0.75)})
    }
    /// Raw median absolute deviation and symmetric trimmed mean.
    pub fn robust(&self, trim: f64) -> Value {
        let n = self.sorted.len();
        let cut = (n as f64 * trim).floor() as usize;
        let kept = &self.sorted[cut..n - cut];
        let trimmed_mean = scaled_mean(kept);
        let mad = quantile(&self.sorted, 0.5).and_then(|median| {
            let scale = self
                .sorted
                .iter()
                .map(|v| v.abs())
                .fold(0., f64::max)
                .max(f64::MIN_POSITIVE);
            let mut deviations: Vec<f64> = self
                .sorted
                .iter()
                .map(|x| {
                    if (x - median).is_finite() {
                        ((x - median) / scale).abs()
                    } else {
                        (x / scale - median / scale).abs()
                    }
                })
                .collect();
            deviations.sort_by(f64::total_cmp);
            quantile(&deviations, 0.5).and_then(|m| finite(m * scale))
        });
        json!({"count":n,"mad":mad,"trimmed_mean":trimmed_mean,
            "trim_fraction":trim,"trimmed_each_tail":cut,"retained_count":kept.len()})
    }
    pub fn outliers(&self) -> Value {
        let bounds = quantile(&self.sorted, 0.25)
            .zip(quantile(&self.sorted, 0.75))
            .map(|(a, b)| {
                let width = 1.5 * (b - a);
                if width.is_finite() {
                    (a - width, b + width)
                } else {
                    // The width can overflow even when a fence remains finite.
                    let scale = a.abs().max(b.abs());
                    let lo = a / scale;
                    let hi = b / scale;
                    (
                        (lo - 1.5 * (hi - lo)) * scale,
                        (hi + 1.5 * (hi - lo)) * scale,
                    )
                }
            });
        let count = bounds.map(|(a, b)| self.sorted.iter().filter(|&&v| v < a || v > b).count());
        json!({"lower":bounds.and_then(|(a,_)|finite(a)),"upper":bounds.and_then(|(_,b)|finite(b)),"count":count,
            "percentage":count.map(|c|100.*c as f64/self.sorted.len() as f64)})
    }
}

fn scaled_mean(sorted: &[f64]) -> Option<f64> {
    let anchor = quantile(sorted, 0.5)?;
    let scale = sorted
        .iter()
        .map(|v| v.abs())
        .fold(0., f64::max)
        .max(f64::MIN_POSITIVE);
    let mean = sum(sorted.iter().map(|x| {
        if (x - anchor).is_finite() {
            (x - anchor) / scale
        } else {
            x / scale - anchor / scale
        }
    })) / sorted.len() as f64;
    finite(anchor + mean * scale)
}

/// Shannon entropy in bits, excluding missing observations.
pub fn entropy(counts: impl Iterator<Item = usize> + Clone) -> Option<f64> {
    let total = counts.clone().sum::<usize>() as f64;
    if total == 0. {
        return None;
    }
    Some(sum(counts.filter(|&n| n > 0).map(|n| {
        let p = n as f64 / total;
        -p * p.log2()
    })))
}

fn centered(values: &[f64]) -> Vec<f64> {
    let anchor = values[0];
    let scale = values
        .iter()
        .map(|v| v.abs())
        .fold(0., f64::max)
        .max(f64::MIN_POSITIVE);
    let mut xs: Vec<f64> = values
        .iter()
        .map(|x| {
            if (x - anchor).is_finite() {
                (x - anchor) / scale
            } else {
                x / scale - anchor / scale
            }
        })
        .collect();
    let mean = sum(xs.iter().copied()) / xs.len() as f64;
    let spread = xs.iter().map(|x| (x - mean).abs()).fold(0., f64::max);
    for x in &mut xs {
        *x = if spread == 0. {
            0.
        } else {
            (*x - mean) / spread
        };
    }
    xs
}
pub fn pearson(x: &[f64], y: &[f64]) -> Option<f64> {
    if x.len() < 2 || x.len() != y.len() {
        return None;
    }
    let a = centered(x);
    let b = centered(y);
    let xx = sum(a.iter().map(|v| v * v));
    let yy = sum(b.iter().map(|v| v * v));
    if xx == 0. || yy == 0. {
        return None;
    }
    finite((sum(a.iter().zip(&b).map(|(a, b)| a * b)) / xx.sqrt() / yy.sqrt()).clamp(-1., 1.))
}
/// Average ranks for ties, with sorting rather than quadratic searches.
pub fn ranks(values: &[f64]) -> Vec<f64> {
    let mut indices: Vec<usize> = (0..values.len()).collect();
    indices.sort_by(|&a, &b| values[a].total_cmp(&values[b]));
    let mut result = vec![0.; values.len()];
    let mut start = 0;
    while start < indices.len() {
        let mut end = start + 1;
        while end < indices.len() && values[indices[start]] == values[indices[end]] {
            end += 1;
        }
        let rank = (start + end + 1) as f64 / 2.;
        for &i in &indices[start..end] {
            result[i] = rank;
        }
        start = end;
    }
    result
}
pub fn correlation(x: &[Option<f64>], y: &[Option<f64>], method: &str) -> Value {
    let pairs: Vec<(f64, f64)> = x.iter().zip(y).filter_map(|(a, b)| a.zip(*b)).collect();
    let (a, b): (Vec<_>, Vec<_>) = pairs.into_iter().unzip();
    let value = if method == "spearman" {
        pearson(&ranks(&a), &ranks(&b))
    } else {
        pearson(&a, &b)
    };
    json!({"value":value,"count":a.len(),"reason":if value.is_some() {None} else if a.len()<2 {Some("fewer than two complete pairs")} else {Some("zero variance in a paired column")}})
}

#[cfg(test)]
mod tests {
    use super::*;
    fn near(a: Option<f64>, b: f64) {
        assert!((a.unwrap() - b).abs() < 1e-10, "{a:?} != {b}");
    }
    #[test]
    fn known_moments() {
        let n = Numeric::new(&[Some(1.), Some(2.), None, Some(3.), Some(4.)]);
        near(n.mean, 2.5);
        near(n.variance, 5. / 3.);
        near(n.std, (5_f64 / 3.).sqrt());
        near(quantile(&n.sorted, 0.25), 1.75);
        near(quantile(&n.sorted, 0.5), 2.5);
        near(quantile(&n.sorted, 0.75), 3.25);
        near(n.skewness, 0.);
        near(n.kurtosis, -1.2);
        assert_eq!(n.describe(1, &[0., 100.])["iqr"], 1.5);
    }
    #[test]
    fn asymmetric_shape_and_custom_percentiles() {
        let skewed = Numeric::new(&[Some(0.), Some(0.), Some(1.)]);
        near(skewed.skewness, 3_f64.sqrt());
        let peaked = Numeric::new(&[Some(0.), Some(0.), Some(0.), Some(1.)]);
        near(peaked.kurtosis, 4.);
        near(quantile(&[1., 2., 3., 4.], 0.1), 1.3);
        near(quantile(&[1., 2., 3., 4.], 0.), 1.);
        near(quantile(&[1., 2., 3., 4.], 1.), 4.);
    }
    #[test]
    fn edges() {
        let empty = Numeric::new(&[None]);
        assert!(empty.mean.is_none());
        let one = Numeric::new(&[Some(2.)]);
        near(one.mean, 2.);
        assert!(one.variance.is_none());
        let constant = Numeric::new(&[Some(3.); 4]);
        near(constant.variance, 0.);
        assert!(constant.skewness.is_none());
        assert!(pearson(&[1., 1.], &[2., 3.]).is_none());
        near(quantile(&[-1e308, 1e308], 0.5), 0.);
        let extreme = Numeric::new(&[Some(-1e308), Some(1e308)]);
        near(extreme.mean, 0.);
        assert!(extreme.std.unwrap().is_finite());
        assert!(extreme.variance.is_none());
        let offset = Numeric::new(&[Some(1e12 + 1.), Some(1e12 + 2.), Some(1e12 + 3.)]);
        near(offset.variance, 1.);
    }
    #[test]
    fn correlations_and_ties() {
        near(pearson(&[1., 2., 3.], &[6., 4., 2.]), -1.);
        assert_eq!(ranks(&[4., 1., 1., 3.]), vec![4., 1.5, 1.5, 3.]);
        let c = correlation(
            &[Some(1.), None, Some(2.), Some(3.)],
            &[Some(10.), Some(0.), Some(20.), Some(100.)],
            "spearman",
        );
        assert_eq!(c["count"], 3);
        near(c["value"].as_f64(), 1.);
    }
    #[test]
    fn robust_and_entropy() {
        let n = Numeric::new(&[Some(1.), Some(2.), None, Some(3.), Some(4.), Some(100.)]);
        let r = n.robust(0.2);
        near(r["mad"].as_f64(), 1.);
        near(r["trimmed_mean"].as_f64(), 3.);
        assert_eq!(r["trimmed_each_tail"], 1);
        near(entropy([2, 2].into_iter()), 1.);
        near(entropy([4].into_iter()), 0.);
        assert!(entropy([0].into_iter()).is_none());
        let extreme = Numeric::new(&[Some(-1e308), Some(1e308)]).robust(0.);
        assert_eq!(extreme["mad"], 1e308);
        assert_eq!(extreme["trimmed_mean"], 0.);
    }
    #[test]
    fn outliers_and_unique() {
        let n = Numeric::new(&[Some(0.), Some(-0.), Some(1.), Some(2.), Some(100.)]);
        assert_eq!(n.unique(), 4);
        assert_eq!(n.outliers()["count"], 1);
        assert_eq!(n.outliers()["percentage"], 20.);
        assert_eq!(n.distribution()["zeros"], 2);
    }
}
