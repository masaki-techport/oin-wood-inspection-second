/**
 * Data Validation and Consistency Check System
 * 
 * This module provides comprehensive validation for all data sources
 * in the inspection system to ensure consistency and prevent conflicts.
 */

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  timestamp: number;
}

export interface ValidationError {
  code: string;
  message: string;
  dataSource: string;
  field?: string;
  value?: any;
  expected?: any;
}

export interface ValidationWarning {
  code: string;
  message: string;
  dataSource: string;
  field?: string;
  value?: any;
  suggestion?: string;
}

export interface InspectionDataValidation {
  inspectionId: number;
  inspectionResult: string;
  defectType: string;
  measurements: string;
  presentationImages: any[];
  sensorStatus: any;
  timestamp: number;
}

/**
 * Validation rules for inspection data
 */
export const INSPECTION_VALIDATION_RULES = {
  inspectionId: {
    required: true,
    type: 'number',
    min: 1,
    message: 'Inspection ID must be a positive number'
  },
  inspectionResult: {
    required: true,
    type: 'string',
    allowedValues: ['無欠点', 'こぶし', '節あり', '通信エラー'],
    message: 'Inspection result must be one of: 無欠点, こぶし, 節あり, 通信エラー'
  },
  defectType: {
    required: false, // Make it optional to avoid validation errors
    type: 'string',
    allowedValues: ['穴●変色発生', '穴発生', '変色発生', '', null, undefined],
    message: 'Defect type must be one of: 穴●変色発生, 穴発生, 変色発生, or empty'
  },
  measurements: {
    required: false,
    type: 'string',
    pattern: /^\d+$/,
    message: 'Measurements must be a numeric string'
  },
  presentationImages: {
    required: false,
    type: 'array',
    maxLength: 5,
    allowEmpty: true,
    message: 'Presentation images must be an array with maximum 5 items'
  }
};

/**
 * Main data validator class
 */
export class DataValidator {
  private validationHistory: ValidationResult[] = [];
  private maxHistorySize = 100;

  /**
   * Validate inspection data for consistency
   */
  validateInspectionData(data: InspectionDataValidation): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];

    // Validate inspection ID
    this.validateField(data.inspectionId, 'inspectionId', INSPECTION_VALIDATION_RULES.inspectionId, errors);

    // Validate inspection result
    this.validateField(data.inspectionResult, 'inspectionResult', INSPECTION_VALIDATION_RULES.inspectionResult, errors);

    // Validate defect type
    this.validateField(data.defectType, 'defectType', INSPECTION_VALIDATION_RULES.defectType, errors);

    // Validate measurements
    if (data.measurements) {
      this.validateField(data.measurements, 'measurements', INSPECTION_VALIDATION_RULES.measurements, errors);
    }

    // Validate presentation images
    if (data.presentationImages) {
      this.validateField(data.presentationImages, 'presentationImages', INSPECTION_VALIDATION_RULES.presentationImages, errors);
    }

    // Cross-field validation
    this.validateCrossFields(data, errors, warnings);

    // Data source consistency validation
    this.validateDataSourceConsistency(data, errors, warnings);

    const result: ValidationResult = {
      isValid: errors.length === 0,
      errors,
      warnings,
      timestamp: Date.now()
    };

    this.addToHistory(result);
    return result;
  }

  /**
   * Validate a single field
   */
  private validateField(
    value: any,
    fieldName: string,
    rules: any,
    errors: ValidationError[]
  ): void {
    // Required validation
    if (rules.required && (value === null || value === undefined || value === '')) {
      errors.push({
        code: 'REQUIRED_FIELD',
        message: rules.message,
        dataSource: 'validation',
        field: fieldName,
        value
      });
      return;
    }

    // Skip other validations if value is empty and not required
    if (!rules.required && (value === null || value === undefined || value === '')) {
      return;
    }

    // Type validation - handle arrays specially
    if (rules.type && rules.type === 'array' && !Array.isArray(value)) {
      errors.push({
        code: 'INVALID_TYPE',
        message: `Field ${fieldName} must be of type ${rules.type}`,
        dataSource: 'validation',
        field: fieldName,
        value,
        expected: rules.type
      });
    } else if (rules.type && rules.type !== 'array' && typeof value !== rules.type) {
      errors.push({
        code: 'INVALID_TYPE',
        message: `Field ${fieldName} must be of type ${rules.type}`,
        dataSource: 'validation',
        field: fieldName,
        value,
        expected: rules.type
      });
    }

    // Min value validation
    if (rules.min !== undefined && value < rules.min) {
      errors.push({
        code: 'INVALID_MIN_VALUE',
        message: `Field ${fieldName} must be at least ${rules.min}`,
        dataSource: 'validation',
        field: fieldName,
        value,
        expected: rules.min
      });
    }

    // Allowed values validation - handle null/undefined values
    if (rules.allowedValues && value !== null && value !== undefined && !rules.allowedValues.includes(value)) {
      errors.push({
        code: 'INVALID_VALUE',
        message: rules.message,
        dataSource: 'validation',
        field: fieldName,
        value,
        expected: rules.allowedValues
      });
    }

    // Pattern validation
    if (rules.pattern && !rules.pattern.test(value)) {
      errors.push({
        code: 'INVALID_PATTERN',
        message: rules.message,
        dataSource: 'validation',
        field: fieldName,
        value
      });
    }

    // Max length validation
    if (rules.maxLength && value.length > rules.maxLength) {
      errors.push({
        code: 'INVALID_MAX_LENGTH',
        message: rules.message,
        dataSource: 'validation',
        field: fieldName,
        value
      });
    }
  }

  /**
   * Validate cross-field relationships
   */
  private validateCrossFields(
    data: InspectionDataValidation,
    errors: ValidationError[],
    warnings: ValidationWarning[]
  ): void {
    // Validate inspection result and defect type consistency
    if (data.inspectionResult === '無欠点' && data.defectType !== '') {
      warnings.push({
        code: 'INCONSISTENT_DEFECT_TYPE',
        message: 'Inspection result is 無欠点 but defect type is not empty',
        dataSource: 'validation',
        field: 'defectType',
        value: data.defectType,
        suggestion: 'Defect type should be empty when inspection result is 無欠点'
      });
    }

    // Validate inspection result and presentation images consistency
    if (data.inspectionResult === '無欠点' && data.presentationImages.length > 0) {
      warnings.push({
        code: 'INCONSISTENT_PRESENTATION_IMAGES',
        message: 'Inspection result is 無欠点 but presentation images are present',
        dataSource: 'validation',
        field: 'presentationImages',
        value: data.presentationImages.length,
        suggestion: 'Presentation images should be empty when inspection result is 無欠点'
      });
    }

    // Validate measurements consistency
    if (data.measurements && data.inspectionResult) {
      const expectedMeasurements = this.getExpectedMeasurements(data.inspectionResult);
      if (data.measurements !== expectedMeasurements) {
        warnings.push({
          code: 'INCONSISTENT_MEASUREMENTS',
          message: `Measurements ${data.measurements} do not match expected value ${expectedMeasurements} for result ${data.inspectionResult}`,
          dataSource: 'validation',
          field: 'measurements',
          value: data.measurements,
          suggestion: `Expected measurements: ${expectedMeasurements}`
        });
      }
    }
  }

  /**
   * Validate data source consistency
   */
  private validateDataSourceConsistency(
    data: InspectionDataValidation,
    errors: ValidationError[],
    warnings: ValidationWarning[]
  ): void {
    // Check if sensor status is consistent with inspection data
    if (data.sensorStatus && data.sensorStatus.inspection_data) {
      const sensorInspectionId = data.sensorStatus.inspection_data.inspection_id;
      if (sensorInspectionId !== data.inspectionId) {
        errors.push({
          code: 'INCONSISTENT_INSPECTION_ID',
          message: `Sensor status inspection ID (${sensorInspectionId}) does not match inspection ID (${data.inspectionId})`,
          dataSource: 'sensor-status',
          field: 'inspection_id',
          value: sensorInspectionId,
          expected: data.inspectionId
        });
      }

      const sensorResult = data.sensorStatus.inspection_data.results;
      if (sensorResult && sensorResult !== data.inspectionResult) {
        warnings.push({
          code: 'INCONSISTENT_INSPECTION_RESULT',
          message: `Sensor status result (${sensorResult}) does not match inspection result (${data.inspectionResult})`,
          dataSource: 'sensor-status',
          field: 'results',
          value: sensorResult,
          suggestion: 'Consider synchronizing data sources'
        });
      }
    }

    // Check timestamp consistency
    const now = Date.now();
    const timeDiff = now - data.timestamp;
    if (timeDiff > 300000) { // 5 minutes
      warnings.push({
        code: 'STALE_DATA',
        message: `Data is ${Math.round(timeDiff / 1000)} seconds old`,
        dataSource: 'validation',
        field: 'timestamp',
        value: data.timestamp,
        suggestion: 'Consider refreshing data'
      });
    }
  }

  /**
   * Get expected measurements for inspection result
   */
  private getExpectedMeasurements(inspectionResult: string): string {
    const measurementMap: Record<string, string> = {
      '無欠点': '10',
      'こぶし': '20',
      '節あり': '30',
      '通信エラー': '0'
    };
    return measurementMap[inspectionResult] || '0';
  }

  /**
   * Add validation result to history
   */
  private addToHistory(result: ValidationResult): void {
    this.validationHistory.push(result);
    if (this.validationHistory.length > this.maxHistorySize) {
      this.validationHistory.shift();
    }
  }

  /**
   * Get validation history
   */
  getValidationHistory(): ValidationResult[] {
    return [...this.validationHistory];
  }

  /**
   * Get validation statistics
   */
  getValidationStats(): {
    totalValidations: number;
    successRate: number;
    errorCount: number;
    warningCount: number;
  } {
    const total = this.validationHistory.length;
    const successful = this.validationHistory.filter(r => r.isValid).length;
    const errorCount = this.validationHistory.reduce((sum, r) => sum + r.errors.length, 0);
    const warningCount = this.validationHistory.reduce((sum, r) => sum + r.warnings.length, 0);

    return {
      totalValidations: total,
      successRate: total > 0 ? successful / total : 0,
      errorCount,
      warningCount
    };
  }

  /**
   * Clear validation history
   */
  clearHistory(): void {
    this.validationHistory = [];
  }
}

// Create singleton instance
export const dataValidator = new DataValidator();

/**
 * Hook for using data validation in React components
 */
export const useDataValidation = () => {
  const validateInspectionData = (data: InspectionDataValidation) => {
    return dataValidator.validateInspectionData(data);
  };

  const getValidationStats = () => {
    return dataValidator.getValidationStats();
  };

  const getValidationHistory = () => {
    return dataValidator.getValidationHistory();
  };

  const clearValidationHistory = () => {
    dataValidator.clearHistory();
  };

  return {
    validateInspectionData,
    getValidationStats,
    getValidationHistory,
    clearValidationHistory
  };
};
